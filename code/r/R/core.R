suppressPackageStartupMessages(library(data.table))
setDTthreads(1)
ROOT <- normalizePath(Sys.getenv("PISA_REPO", "."))
RR <- file.path(ROOT, "code", "r")
OUT <- file.path(ROOT, "results", "r")
INTERIM <- file.path(ROOT, "data", "interim", "r")
CACHE <- file.path(INTERIM, "cache")
REFERENCE <- file.path(ROOT, "reference")
REFERENCE_TABLES <- file.path(INTERIM, "reference")
AUDIT <- file.path(ROOT, "audit")
for (p in c(CACHE, REFERENCE_TABLES, file.path(AUDIT,"tables"), file.path(OUT,c("tables","figures")))) dir.create(p,recursive=TRUE,showWarnings=FALSE)
Rcpp::sourceCpp(file.path(RR,"R/kernels.cpp"), cacheDir=file.path(CACHE,"Rcpp"))
DOMAINS <- c("math","read","scie")
BIN <- sprintf("st250q%02dja",1:5)
CNT4 <- sprintf("st251q%02dja",c(1,3,4,6,7))
DEV <- sprintf("st254q%02dja",1:5)
COMMON <- c(BIN,CNT4,DEV,"st255q01ja")
BT <- sprintf("st256q%02dja",c(1,2,3,6,7,8,9,10))
DROP <- c("st253q01ja","st254q06ja","st251q02ja")
NAT <- sprintf("st250q%02dda",c(8:16,18:28))
pvcols <- function(dom) paste0("pv",1:10,dom)
allpv <- unlist(lapply(DOMAINS,pvcols))
write_table <- function(x,name) fwrite(as.data.table(x),file.path(OUT,"tables",paste0(name,".csv")),na="")
read_table <- function(name) fread(file.path(OUT,"tables",paste0(name,".csv")))
write_diagnostic <- function(x,name) fwrite(as.data.table(x),file.path(AUDIT,"tables",paste0(name,".csv")),na="")
read_diagnostic <- function(name) fread(file.path(AUDIT,"tables",paste0(name,".csv")))
write_reference_table <- function(x,name) fwrite(as.data.table(x),file.path(REFERENCE_TABLES,paste0(name,".csv")),na="")
read_reference_table <- function(name) fread(file.path(REFERENCE_TABLES,paste0(name,".csv")))
save_cache <- function(x,name) saveRDS(x,file.path(INTERIM,paste0(name,".rds")),compress=FALSE)
load_cache <- function(name) readRDS(file.path(INTERIM,paste0(name,".rds")))
read_extract <- function(year,cols=NULL) {
  path<-file.path(ROOT,"data/extract",paste0("stu_",year,".parquet"))
  d <- as.data.table(if(is.null(cols)) arrow::read_parquet(path) else arrow::read_parquet(path,col_select=tidyselect::all_of(cols)))
  d[,raw_row:=seq_len(.N)]; d
}

# Native NPY reader (NumPy v1/v2, little-endian float64, C or Fortran order).
# Retain source row numbers and read only selected contiguous runs.
read_weights <- function(year,rows) {
  path <- file.path(ROOT,"data/extract",paste0("wts_",year,".npy"))
  con <- file(path,"rb"); on.exit(close(con))
  magic <- readBin(con,"raw",6); stopifnot(identical(magic,as.raw(c(147,78,85,77,80,89))))
  ver <- readBin(con,"integer",2,size=1,signed=FALSE)
  hl <- readBin(con,"integer",1,size=if(ver[1]==1) 2 else 4,signed=if(ver[1]==1) FALSE else TRUE,endian="little")
  hdr <- rawToChar(readBin(con,"raw",hl)); offset <- seek(con)
  stopifnot(grepl("'<f8'",hdr,fixed=TRUE))
  fortran<-grepl("'fortran_order': True",hdr,fixed=TRUE)
  shape <- strsplit(sub(".*'shape': \\(([^)]+)\\).*","\\1",hdr),",")[[1]]
  shape <- as.integer(trimws(shape[nzchar(trimws(shape))])); stopifnot(length(shape)==2,shape[2]==80)
  stopifnot(all(rows>=1 & rows<=shape[1]),!anyDuplicated(rows))
  o <- order(rows); rr <- rows[o]; ans <- matrix(NA_real_,length(rows),80)
  starts <- c(1L,which(diff(rr)!=1)+1L); ends <- c(starts[-1]-1L,length(rr))
  if(fortran) {
    for(j in 1:80) {
      for(i in seq_along(starts)) {
        a<-starts[i];b<-ends[i]
        seek(con,offset+((j-1)*shape[1]+rr[a]-1)*8,origin="start")
        column<-readBin(con,"double",b-a+1,size=8,endian="little")
        stopifnot(length(column)==b-a+1);ans[o[a:b],j]<-column
      }
    }
    stopifnot(all(is.finite(ans)),all(ans>=0))
    return(ans)
  }
  for(i in seq_along(starts)) {
    a<-starts[i]; b<-ends[i]; seek(con,offset+(rr[a]-1)*80*8,origin="start")
    values <- readBin(con,"double",(b-a+1)*80,size=8,endian="little")
    stopifnot(length(values)==(b-a+1)*80)
    ans[o[a:b],] <- matrix(values,ncol=80,byrow=TRUE)
  }
  stopifnot(all(is.finite(ans)),all(ans>=0)); ans
}
weights_for <- function(g) {
  stopifnot(uniqueN(g$wave)==1)
  if("supplement"%in%names(g)&&any(g$supplement)) {
    stopifnot(all(g$supplement))
    W<-readRDS(file.path(CACHE,paste0("weights_supplement_",g$wave[1],".rds")))
    return(cbind(g$w_fstuwt,W[g$raw_row,,drop=FALSE]))
  }
  cbind(g$w_fstuwt,read_weights(g$wave[1],g$raw_row))
}
wmean <- function(x,w) {m<-is.finite(x)&is.finite(w)&w>0; if(!any(m)) return(NA_real_); sum(x[m]*w[m])/sum(w[m])}
wcorr <- function(x,y,w,min_n=100) {
  m<-is.finite(x)&is.finite(y)&is.finite(w)&w>0
  if(sum(m)<min_n) return(NA_real_)
  x<-x[m];y<-y[m];w<-w[m];x<-x-wmean(x,w);y<-y-wmean(y,w)
  den<-sqrt(sum(w*x*x)*sum(w*y*y)); if(den==0) NA_real_ else sum(w*x*y)/den
}
zscore <- function(x,w,mask=rep(TRUE,length(x))) {
  m<-mask&is.finite(x)&is.finite(w)&w>0; mu<-wmean(x[m],w[m]); s<-sqrt(wmean((x[m]-mu)^2,w[m]))
  if(!is.finite(s)||s==0) return(rep(NA_real_,length(x))); (x-mu)/s
}
# Group IDs preserve the original cell order used by the Python imputation.
cell_id <- function(d) match(paste(d$cnt,d$wave),unique(paste(d$cnt,d$wave)))
senate <- function(d) d$w_fstuwt / ave(d$w_fstuwt,cell_id(d),FUN=sum)
recode_values <- function(x,valid) {x[!x%in%valid]<-NA_real_; x}
binary <- function(x) {x<-recode_values(x,1:2); 2-x}

quantile_codes <- function(x,W,k=4,mode="replicate",seed=7) {
  stopifnot(all(is.finite(x)),all(is.finite(W)),all(W>=0),all(colSums(W)>0))
  set.seed(seed); o<-order(x,runif(length(x)))
  stopifnot(mode%in%c("replicate","paper","fixed"))
  R <- if(mode=="fixed") 1L else ncol(W)
  out<-matrix(0L,length(x),R)
  for(r in seq_len(R)) {
    before<-c(0,head(cumsum(W[o,r]),-1))/sum(W[,r])
    # Replicated cut points reproduce the SEs of the published trend tables.
    # Fixed groups are retained as a diagnostic, not assumed from recoding alone.
    out[o,r]<-findInterval(before,(1:(k-1))/k,left.open=mode!="fixed")
  }
  out
}
theta_quartiles <- function(x,W,P,k=4,mode="replicate",seed=7) group_means_cpp(quantile_codes(x,W,k,mode,seed),W,P,k)
theta_groups <- function(code,W,P,k) group_means_cpp(matrix(as.integer(code),ncol=1),W,P,k)
summarise_theta <- function(th) {
  K<-dim(th)[1]; R<-dim(th)[2]-1; M<-dim(th)[3]
  t0<-matrix(th[,1,],K,M); mu<-rowMeans(t0); V<-matrix(0,K,K)
  for(m in seq_len(M)) {delta<-matrix(th[,-1,m],K,R)-t0[,m]; V<-V+tcrossprod(delta)/(R*.25*M)}
  if(M>1) V<-V+(1+1/M)*tcrossprod(t0-mu)/(M-1)
  list(estimate=mu,covariance=V,se=sqrt(pmax(0,diag(V))))
}
pool_theta <- function(ths,method="independent") {
  stopifnot(length(ths)>0)
  if(method=="paper") return(summarise_theta(Reduce(`+`,ths)/length(ths)))
  s<-lapply(ths,summarise_theta); n<-length(s)
  V<-Reduce(`+`,lapply(s,`[[`,"covariance"))/n^2
  list(estimate=Reduce(`+`,lapply(s,`[[`,"estimate"))/n,covariance=V,se=sqrt(pmax(0,diag(V))))
}
contrast <- function(s,c) c(estimate=sum(s$estimate*c),se=sqrt(max(0,drop(t(c)%*%s$covariance%*%c))))

escs <- function(X,group,w,imputation="regression",noise=TRUE,seed=20252022) {
  X<-as.matrix(X); missing<-!is.finite(X); nm<-rowSums(missing); imp<-rep(FALSE,nrow(X)); set.seed(seed)
  if(imputation=="regression") {
    for(g in sort(unique(group))) {
      ii<-which(group==g); complete<-ii[nm[ii]==0]
      if(length(complete)<30) next
      for(j in 1:3) {
        target<-ii[nm[ii]==1 & missing[ii,j]]; if(!length(target)) next
        A<-cbind(1,X[complete,-j,drop=FALSE]); fit<-lm.fit(A,X[complete,j])
        stopifnot(fit$rank==ncol(A)); b<-fit$coefficients
        sd<-sqrt(sum(fit$residuals^2)/(length(complete)-fit$rank))
        X[target,j]<-drop(cbind(1,X[target,-j,drop=FALSE])%*%b)+if(noise) rnorm(length(target),0,sd) else 0
        imp[target]<-TRUE
      }
    }
    X[nm>=2,]<-NA_real_
  }
  Z<-vapply(1:3,function(j) zscore(X[,j],w),numeric(nrow(X)))
  s<-if(imputation=="mean") rowMeans(Z,na.rm=TRUE) else rowMeans(Z)
  s[nm>=2]<-NA_real_; if(imputation=="complete") s[nm>0]<-NA_real_
  list(score=zscore(s,w),Z=Z,pct_imputed=mean(imp)*100)
}
pca_score <- function(X,w,mask=rep(TRUE,nrow(X))) {
  n<-rowSums(is.finite(X)); full<-n==3 & mask
  v<-eigen(cov.wt(X[full,,drop=FALSE],wt=w[full])$cov,symmetric=TRUE)$vectors[,1]
  if(v[1]<0) v<- -v; Xi<-X; Xi[!is.finite(Xi)]<-0
  s<-drop(Xi%*%v);s[n<2|!mask]<-NA_real_;list(score=s,loadings=v)
}
