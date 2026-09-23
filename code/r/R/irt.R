gpcm_probs <- function(a,b,theta) {
  k<-0:length(b); z<-a*(outer(k,theta)-c(0,cumsum(b)))
  z<-sweep(z,2,apply(z,2,max)); p<-exp(z);sweep(p,2,colSums(p),`/`)
}
warm_terms <- function(theta,response,a,b) {
  observed<-which(is.finite(response)&response>=0);ll<-score<-info<-di<-0
  for(j in observed) {
    p<-as.numeric(gpcm_probs(a[j],b[[j]],theta));k<-seq_along(p)-1;mu<-sum(k*p)
    score<-score+a[j]*(response[j]-mu);info<-info+a[j]^2*sum(p*(k-mu)^2)
    di<-di+a[j]^3*sum(p*(k-mu)^3);ll<-ll+log(p[response[j]+1])
  }
  c(equation=score+di/(2*info),objective=ll+.5*log(info))
}
resolve_wle <- function(scored,X,a,b,bound=12) {
  valid<-rowSums(X>=0,na.rm=TRUE)>=3
  failed<-which(valid&(!scored$converged|scored$boundary))
  # Warm's objective need not be globally concave. Bracket every stationary
  # point for the few cases where Newton iteration fails, then select its maximum.
  for(i in failed) {
    grid<-seq(-bound,bound,by=.25)
    f<-function(t)warm_terms(t,X[i,],a,b)
    v<-vapply(grid,function(t)f(t)[1],numeric(1))
    intervals<-which(head(v,-1)*tail(v,-1)<=0)
    roots<-vapply(intervals,function(j)uniroot(function(t)f(t)[1],grid[c(j,j+1)],tol=1e-10)$root,numeric(1))
    if(!length(roots))next
    theta<-roots[which.max(vapply(roots,function(t)f(t)[2],numeric(1)))]
    scored$theta[i]<-theta;scored$equation[i]<-f(theta)[1]
    scored$converged[i]<-abs(scored$equation[i])<1e-6;scored$boundary[i]<-abs(theta)>=bound
  }
  scored$fallback_n<-length(failed);scored
}
fit_irt <- function(X,w,name,maxit=300,tol=1e-3) {
  storage.mode(X)<-"integer"; X[is.na(X)]<- -1L
  J<-ncol(X); nodes<-seq(-4,4,length.out=25); prior<-dnorm(nodes); prior<-prior/sum(prior)
  a<-rep(1,J); b<-lapply(1:J,function(j) {
    tab<-tabulate(X[X[,j]>=0,j]+1); p<-rev(cumsum(rev(tab)))[-1]/sum(tab)
    pmax(-3.5,pmin(3.5,-qlogis(p)))
  })
  history<-list(); converged<-FALSE
  for(it in seq_len(maxit)) {
    E<-expectation_cpp(X,w,a,b,nodes,prior); change<-0; failures<-0L
    for(j in 1:J) {
      r<-E$counts[[j]]; K<-nrow(r); k<-0:(K-1)
      objective<-function(par,gradient=FALSE) {
        aa<-exp(par[1]);bb<-par[-1];P<-gpcm_probs(aa,bb,nodes)
        if(!gradient) return(-sum(r*log(pmax(P,1e-300))))
        U<-outer(k,nodes)-c(0,cumsum(bb)); ga<- -sum(r*sweep(U,2,colSums(P*U)))*aa
        gb<-vapply(1:(K-1),function(v) {dz<- -aa*(k>=v); -sum(r*sweep(matrix(dz,K,length(nodes)),2,colSums(P*dz)))},numeric(1))
        c(ga,gb)
      }
      opt<-optim(c(log(a[j]),b[[j]]),objective,function(p) objective(p,TRUE),method="L-BFGS-B",control=list(maxit=200,factr=4.5e5,pgtol=1e-6))
      failures<-failures+as.integer(opt$convergence!=0)
      aa<-exp(opt$par[1]);bb<-opt$par[-1]
      change<-max(change,abs(aa-a[j]),abs(bb-b[[j]]));a[j]<-aa;b[[j]]<-bb
    }
    history[[it]]<-data.table(iteration=it,loglik=E$loglik,max_change=change,optimizer_failures=failures)
    cat(sprintf("%s iteration %d: change %.6f, log likelihood %.2f\n",name,it,change,E$loglik));flush.console()
    if(it==60) save_cache(list(a=a,b=b),paste0(name,"_iteration60"))
    if(change<tol && failures==0) {converged<-TRUE;break}
  }
  history<-rbindlist(history);write_diagnostic(history,paste0(name,"_convergence"))
  model<-list(a=a,b=b,nodes=nodes,prior=prior,converged=converged,iterations=it,history=history)
  save_cache(model,paste0(name,"_model"))
  if(!converged) stop("IRT did not converge: ",name,". Inspect the convergence table before scoring.")
  model
}
fit_and_score <- function(d,items,min_items,name) {
  X<-as.matrix(d[,..items]); storage.mode(X)<-"integer"; X[is.na(X)]<- -1L
  w<-senate(d);w<-w/sum(w)*nrow(d)
  model_path<-file.path(INTERIM,paste0(name,"_model.rds"))
  fingerprint<-digest::digest(list(X,w,body(fit_irt)),algo="xxhash64")
  model<-if(file.exists(model_path)) readRDS(model_path) else NULL
  if(is.null(model)||!isTRUE(model$converged)||!identical(model$fingerprint,fingerprint)) {
    model<-fit_irt(X,w,name);model$fingerprint<-fingerprint;save_cache(model,paste0(name,"_model"))
  }
  scored<-resolve_wle(wle_cpp(X,model$a,model$b,min_items=3),X,model$a,model$b)
  valid<-rowSums(X>=0)>=3
  write_diagnostic(data.table(model=name,n=nrow(X),eligible=sum(valid),fallback_n=scored$fallback_n,not_converged=sum(valid&!scored$converged),boundary=sum(scored$boundary)),paste0(name,"_scoring_diagnostics"))
  if(any(valid&(!scored$converged|scored$boundary))) stop("Unresolved WLE scores in ",name)
  parameter_table<-switch(name,irt16="irt_parameters",irt13="irt_parameters_four_cycles",irt13_oecd35="irt_parameters_four_cycles_oecd35",paste0(name,"_parameters"))
  write_table(data.table(item=items,a=model$a,steps=vapply(model$b,function(z) jsonlite::toJSON(z,digits=16),character(1))),parameter_table)
  score<-scored$theta;score[rowSums(X>=0)<min_items]<-NA_real_
  list(score=score,score3=scored$theta,model=model)
}

build_base <- function() {
  parts<-lapply(c(2022,2025),read_extract)
  both<-intersect(parts[[1]]$cnt,parts[[2]]$cnt)
  d<-rbindlist(parts,fill=TRUE);rm(parts);gc(FALSE)
  write_diagnostic(d[,.(n=.N,escs_valid=sum(is.finite(escs)),hisei_valid=sum(is.finite(hisei)),pared_valid=sum(is.finite(paredint)),homepos_valid=sum(is.finite(homepos))),by=.(cnt,wave)],"input_coverage")
  d<-d[cnt%in%both];d[,in_sample:=cnt!="CRI"]
  setorderv(d,"in_sample",-1L)
  for(v in c(BIN,NAT)) set(d,j=v,value=binary(d[[v]]))
  for(v in c(CNT4,DEV,BT,"st254q06ja","st251q02ja")) set(d,j=v,value=recode_values(d[[v]],1:4))
  d[,st253q01ja:=recode_values(st253q01ja,1:8)]
  d[,st255q01ja:=recode_values(st255q01ja,1:7)]
  d[,books7:=st255q01ja]
  Z<-scale(as.matrix(d[,..COMMON])); nc<-rowSums(is.finite(Z)); cp<-rowMeans(Z,na.rm=TRUE);cp[nc<10]<-NA_real_
  d[,`:=`(cpos=cp,n_common=nc)]
  b<-as.matrix(d[,..BT]); s<-rowSums(b>=2,na.rm=TRUE);s[rowSums(is.finite(b))<6]<-NA_real_;d[,n_booktypes:=s]
  b<-as.matrix(d[,..NAT]);s<-rowSums(b,na.rm=TRUE);nc<-rowSums(is.finite(b));s[nc==0]<-NA_real_
  d[,`:=`(n_national_yes=s,n_national_adm=nc,math=rowMeans(.SD,na.rm=TRUE)),.SDcols=pvcols("math")]
  stopifnot(!anyDuplicated(d[,.(wave,cnt,cntstuid)]),all(d$w_fstuwt>0))
  save_cache(d,"base")
  # IRT categories are zero based, while the descriptive base keeps questionnaire categories.
  cal<-copy(d[,c("wave","cnt","w_fstuwt",COMMON),with=FALSE])
  for(v in setdiff(COMMON,BIN)) set(cal,j=v,value=cal[[v]]-1)
  ir<-fit_and_score(cal,COMMON,10,"irt16");rm(cal);gc(FALSE)
  d[,`:=`(homepos_irt=ir$score,homepos_irt3=ir$score3)]
  s<-d[in_sample==TRUE];w<-senate(s);s[,pared_c:=fifelse(paredint==3,6,fifelse(paredint==14.5,14,paredint))]
  for(pair in list(c("hisei_h","hisei"),c("pared_h","pared_c"),c("homepos_h","homepos_irt"),c("books_h","books7"))) set(s,j=pair[1],value=zscore(s[[pair[2]]],w))
  raw<-as.matrix(s[,.(hisei,pared_c,homepos_irt)])
  sc<-escs(raw,cell_id(s),w);s[,escs_h:=sc$score]
  X<-as.matrix(s[,.(hisei_h,pared_h,homepos_h)]);s[,escs_pca:=zscore(pca_score(X,w)$score,w)]
  sc3<-escs(as.matrix(s[,.(hisei,pared_c,homepos_irt3)]),cell_id(s),w);s[,escs_h_min3:=sc3$score]
  save_cache(s,"analysis"); save_cache(d,"base_scored")
  write_diagnostic(data.table(n=nrow(s),imputed_pct=sc$pct_imputed,coverage_pct=mean(is.finite(s$escs_h))*100),"composite_diagnostics")
  invisible(s)
}

recode_four <- function(g) {
  old<-g$wave[1]<=2018
  defs<-list(room=c("st011q02ta","st250q01ja","bin"),computer=c("st011q04ta","st250q02ja","bin"),
    software=c("st011q05ta","st250q03ja","bin"),internet=c("st011q06ta","st250q05ja","bin"),
    art=c("st011q09ta","st251q07ja","art"),instruments=c("st012q09na","st251q06ja","count"),
    cars=c("st012q02ta","st251q01ja","count"),bathrooms=c("st012q03ta","st251q03ja","count"),
    televisions=c("st012q01ta","st254q01ja","band"),tablets=c("st012q07na","st254q04ja","band"),
    ereaders=c("st012q08na","st254q05ja","band"),computers=c("st012q06na","st254q02ja","computers"),books=c("books6","st255q01ja","books"))
  out<-list()
  for(nm in names(defs)) {
    def<-defs[[nm]];x<-g[[def[if(old)1 else 2]]];kind<-def[3]
    if(kind=="bin"||(kind=="art"&&old)) v<-binary(x)
    else if(kind=="art") v<-as.numeric(recode_values(x,1:4)>1)
    else if(kind=="count") v<-recode_values(x,1:4)-1
    else if(kind=="band") v<-if(old) c(0,1,1,2)[match(x,1:4)] else c(0,1,2,2)[match(x,1:4)]
    else if(kind=="books") v<-if(old) recode_values(x,1:6)-1 else pmax(1,recode_values(x,1:7)-1)-1
    else if(old) v<-as.numeric(recode_values(x,1:4)>=2)
    else {
      a<-recode_values(x,1:4);b<-recode_values(g$st254q03ja,1:4)
      # Unknown plus none is unknown, not an observed absence of a computer.
      v<-rep(NA_real_,length(a));v[which(a>=2|b>=2)]<-1;v[which(a==1&b==1)]<-0
    }
    out[[nm]]<-v
  }
  as.data.table(out)
}
build_four <- function(scope="paper") {
  parts<-lapply(c(2015,2018,2022,2025),function(y) {
    g<-read_extract(y);g[,supplement:=FALSE]
    if(scope=="oecd35" && y==2015) {
      supp<-readRDS(file.path(CACHE,"students_supplement_2015.rds"))
      g<-rbindlist(list(g,supp),fill=TRUE)
    }
    it<-recode_four(g)
    keep<-c("wave","cnt","cntstuid","raw_row","supplement","w_fstuwt","escs","homepos","hisei","paredint","hisced",allpv)
    cbind(g[,..keep],it)
  })
  common<-if(scope=="paper") setdiff(Reduce(intersect,lapply(parts,function(g) unique(g$cnt))),"CRI") else setdiff(names(COUNTRY_NAMES),c("CRI","LUX","ESP"))
  if(scope=="oecd35") stopifnot(all(vapply(parts,function(g) all(common%in%g$cnt),logical(1))))
  d<-rbindlist(parts,fill=TRUE);rm(parts);d<-d[cnt%in%common];gc(FALSE)
  trend<-readRDS(file.path(CACHE,"official_trend_indices.rds"))
  d[,cntstuid:=as.character(cntstuid)]
  # Trend CSV uses the within-country student ID; PUF prefixes the numeric country code.
  within_id<-as.character(as.numeric(d$cntstuid)%%100000)
  stopifnot(!anyDuplicated(paste(d$wave,d$cnt,within_id)))
  pos<-match(paste(d$wave,d$cnt,within_id),paste(trend$wave,trend$cnt,trend$cntstuid))
  for(v in c("escs","homepos")) {
    values<-d[[v]];old<-d$wave<=2018
    stopifnot(all(!is.na(pos[old])))
    values[old]<-trend[[paste0(v,"_trend2022")]][pos[old]]
    set(d,j=paste0(v,"_trend2022"),value=values)
  }
  mapping<-d[wave==2018 & is.finite(hisced)&is.finite(paredint),.(years=as.numeric(names(sort(table(paredint),decreasing=TRUE))[1])),by=hisced]
  d[wave==2015,paredint:=mapping$years[match(hisced,mapping$hisced)]]
  d[,pared_c:=fifelse(paredint==3,6,fifelse(paredint==14.5,14,paredint))]
  if(scope=="oecd35") {
    old<-which(d$wave<=2018)
    d[old,hisei:=trend$hisei_trend2022[pos[old]]]
    d[old,pared_c:=trend$pared_trend2022[pos[old]]]
    d[,pared_c:=fifelse(pared_c==3,6,fifelse(pared_c==14.5,14,pared_c))]
  }
  items<-c("room","computer","software","internet","art","instruments","cars","bathrooms","televisions","tablets","ereaders","computers","books")
  ir<-fit_and_score(d,items,8,if(scope=="paper")"irt13" else "irt13_oecd35");w<-senate(d)
  d[,`:=`(homepos_h4=zscore(ir$score,w),hisei_h4=zscore(hisei,w),pared_h4=zscore(pared_c,w))]
  raw<-cbind(d$hisei,d$pared_c,ir$score);group<-cell_id(d)
  d[,escs_h4:=escs(raw,group,w)$score];d[,escs_mean4:=escs(raw,group,w,imputation="mean")$score]
  d[,escs_pca4:=pca_score(as.matrix(.SD),w)$score,.SDcols=c("hisei_h4","pared_h4","homepos_h4")]
  save_cache(d,if(scope=="paper")"four" else "four_oecd35");write_table(mapping,"hisced_mapping_2015")
  invisible(d)
}
