item_labels <- function() {
  # Labels are metadata only; all statistics and recoding are implemented in R.
  labs<-c("A room of your own","Computer for schoolwork","Educational software","Own phone with internet","Internet access","Cars","Bathrooms","Flush toilets","Musical instruments","Works of art","Televisions","Desktop computers","Laptops","Tablets","E-book readers","Books at home (number)","Religious books","Classical literature","Contemporary literature","Science books","Art/music/design books","Technical reference books","Dictionaries","Books for schoolwork","Screen devices (number)","Cell phones (number)","Mopeds/motorcycles","Electric lighting","Plumbed water","Off-street parking","Garbage collection","Stove/burner","Table for meals","Vacuum cleaner","Refrigerator","Sewer connection","Air conditioning/heating","Guest room","Quiet place to study","Swimming pool/jacuzzi","Security system","Smart TV","Dishwasher","Own tablet","TV/streaming subscription","Domestic workers","Newspaper subscription")
  setNames(labs,c(COMMON,BT,DROP,NAT))
}
mean_correlation <- function(d,a,b) {
  vals<-d[,.(r=wcorr(get(a),get(b),w_fstuwt)),by=cnt]$r
  if(all(is.na(vals))) NA_real_ else mean(vals,na.rm=TRUE)
}
achievement_corr <- function(d,a,dom,use_pv=TRUE) {
  vars<-if(use_pv) pvcols(dom) else "score"
  mean(vapply(vars,function(b) mean_correlation(d,a,b),numeric(1)),na.rm=TRUE)
}
validate_item <- function(d,item,dom,use_pv=TRUE) {
  vars<-if(use_pv) pvcols(dom) else "score";out<-list();i<-0L
  needed<-unique(c("cnt",item,vars,"hisei","paredint","w_fstuwt"));d<-d[,..needed]
  for(g in split(d,by="cnt")) {
    same_mask<-all(vapply(vars,function(v)identical(is.finite(g[[v]]),is.finite(g[[vars[1]]])),logical(1)))
    if(same_mask) {
      keep<-complete.cases(g[,c(item,vars,"hisei","paredint","w_fstuwt"),with=FALSE]);x<-g[keep]
      if(nrow(x)<100||uniqueN(x[[item]])<2)next
      w<-x$w_fstuwt;A<-cbind(1,x$hisei,x$paredint)
      residual<-lm.wfit(A,as.matrix(x[,c(item,vars),with=FALSE]),w)$residuals
      hi<-wcorr(x[[item]],x$hisei,w);pa<-wcorr(x[[item]],x$paredint,w)
      for(j in seq_along(vars)) {
        i<-i+1L;out[[i]]<-c(r_score_cc=wcorr(x[[item]],x[[vars[j]]],w),r_hisei=hi,r_pared=pa,partial_r=if(use_pv)wcorr(residual[,1],residual[,j+1],w)else cor(residual[,1]*sqrt(w),residual[,j+1]*sqrt(w)))
      }
      next
    }
    for(score in vars) {
    keep<-complete.cases(g[,c(item,score,"hisei","paredint","w_fstuwt"),with=FALSE]);x<-g[keep]
    if(nrow(x)<100||uniqueN(x[[item]])<2) next
    w<-x$w_fstuwt;A<-cbind(1,x$hisei,x$paredint)
    rx<-lm.wfit(A,x[[item]],w)$residuals;ry<-lm.wfit(A,x[[score]],w)$residuals
    i<-i+1L;out[[i]]<-c(r_score_cc=wcorr(x[[item]],x[[score]],w),r_hisei=wcorr(x[[item]],x$hisei,w),r_pared=wcorr(x[[item]],x$paredint,w),partial_r=if(use_pv) wcorr(rx,ry,w) else cor(rx*sqrt(w),ry*sqrt(w)))
    }
  }
  if(!length(out)) return(as.list(setNames(rep(NA_real_,4),c("r_score_cc","r_hisei","r_pared","partial_r"))))
  as.list(colMeans(do.call(rbind,out),na.rm=TRUE))
}
run_items <- function(d,dom,use_pv=TRUE) {
  d<-copy(d);d[,score:=rowMeans(.SD),.SDcols=pvcols(dom)]
  labels<-item_labels();suf<-if(use_pv) "" else "_paper_protocol"
  parts<-split(d,by="wave",keep.by=TRUE); rows<-list();i<-0L
  for(v in c(COMMON,BT,DROP,NAT)) for(y in c(2022,2025)) {
    if((y==2022&&v%in%NAT)||(y==2025&&v%in%c(BT,DROP))) next
    g<-parts[[as.character(y)]];r<-achievement_corr(g,v,dom,use_pv)
    if(!is.finite(r)) next
    i<-i+1L;rows[[i]]<-as.data.table(c(list(item=toupper(v),label=labels[[v]],group=if(v%in%COMMON)"common" else if(v%in%NAT)"2025 only" else "2022 only",wave=y,r_score=r),validate_item(g,v,dom,use_pv)))
  }
  t<-rbindlist(rows);write_table(t,paste0("items_validation_",dom,suf))
  gr<-t[,c(list(n_items=.N),lapply(.SD,mean,na.rm=TRUE)),by=.(group,wave),.SDcols=c("r_score","r_score_cc","r_hisei","r_pared","partial_r")]
  write_table(gr,paste0("items_validation_groups_",dom,suf))
  g<-parts[["2025"]];rows<-list()
  for(v in NAT) {
    n<-g[is.finite(get(v)),.(pct=100*wmean(get(v),w_fstuwt),n=.N),by=cnt][n>=100]
    rows[[v]]<-data.table(item=toupper(v),label=labels[[v]],pct_yes=mean(n$pct),n_systems=nrow(n),r_score=achievement_corr(g,v,dom,use_pv))
  }
  national<-rbindlist(rows);setorder(national,-pct_yes);write_table(national,paste0("national_items_",dom,suf))
  adm<-g[,lapply(.SD,function(x) as.integer(sum(is.finite(x))>=100)),by=cnt,.SDcols=NAT]
  setnames(adm,NAT,toupper(NAT));write_table(adm,"national_items_by_system")
  SUB<-list("Cultural: books, book types, instruments, art"=c("st255q01ja",BT,"st251q06ja","st251q07ja"),"Living conditions: own room, internet, cars, bathrooms, toilets"=c("st250q01ja","st250q05ja","st251q01ja","st251q03ja","st251q04ja"),"Technology: computer, software, phone, devices"=c("st250q02ja","st250q03ja","st250q04ja",DEV,"st253q01ja","st254q06ja"))
  g<-parts[["2022"]];rows<-list()
  for(nm in names(SUB)) {
    vars<-SUB[[nm]];Z<-vapply(vars,function(v) zscore(g[[v]],g$w_fstuwt),numeric(nrow(g)))
    g[,subscore:=rowMeans(Z,na.rm=TRUE)];g[rowSums(is.finite(Z))<max(2,floor(length(vars)/2)),subscore:=NA_real_]
    gaps<-g[is.finite(subscore),{q<-quantile_codes(subscore,matrix(w_fstuwt))[,1];list(gap=wmean(score[q==3],w_fstuwt[q==3])-wmean(score[q==0],w_fstuwt[q==0]))},by=cnt]$gap
    rows[[nm]]<-data.table(subscale=nm,r_score=achievement_corr(g,"subscore",dom,use_pv),r_homepos_pub=mean_correlation(g,"subscore","homepos"),r_homepos_har=mean_correlation(g,"subscore","homepos_h"),gap_q4_q1=mean(gaps))
  };write_table(rbindlist(rows),paste0("subscales_2022_",dom,suf))
  rows<-list()
  for(y in c(2022,2025)) {
    g<-parts[[as.character(y)]];Z<-vapply(COMMON,function(v) zscore(g[[v]],g$w_fstuwt),numeric(nrow(g)))
    ok<-complete.cases(Z)&is.finite(g$homepos);fit<-lm.wfit(cbind(1,Z[ok,]),g$homepos[ok],g$w_fstuwt[ok])
    residual<-rep(NA_real_,nrow(g));residual[ok]<-fit$residuals;g[,residual:=residual]
    r2<-1-wmean(fit$residuals^2,g$w_fstuwt[ok])/wmean((g$homepos[ok]-wmean(g$homepos[ok],g$w_fstuwt[ok]))^2,g$w_fstuwt[ok])
    rows[[as.character(y)]]<-data.table(wave=y,r2_common_items=r2,res_r_score=achievement_corr(g,"residual",dom,use_pv),res_r_booktypes=if(y==2022)mean_correlation(g,"residual","n_booktypes") else NA_real_,res_r_national_yes=if(y==2025)mean_correlation(g,"residual","n_national_yes") else NA_real_,res_r_hisei=mean_correlation(g,"residual","hisei"))
  };write_table(rbindlist(rows),paste0("homepos_residual_",dom,suf))
}
run_correlations <- function(d,dom,use_pv=TRUE) {
  d<-copy(d);d[,score:=rowMeans(.SD),.SDcols=pvcols(dom)];rows<-list();i<-0L
  for(tag in c("published","harmonized")) {
    vars<-if(tag=="published")c("hisei","paredint","homepos") else c("hisei_h","pared_h","homepos_h")
    pairs<-list(c(1,2),c(1,3),c(2,3),c(1,4),c(2,4),c(3,4));namesp<-c("HISEI - PARED","HISEI - HOMEPOS","PARED - HOMEPOS","HISEI - achievement","PARED - achievement","HOMEPOS - achievement")
    for(j in seq_along(pairs)) {
      p<-pairs[[j]];a<-vars[p[1]]
      r<-vapply(c(2022,2025),function(y) {g<-d[wave==y];if(p[2]==4) achievement_corr(g,a,dom,use_pv) else mean_correlation(g,a,vars[p[2]])},numeric(1))
      i<-i+1L;rows[[i]]<-data.table(version=tag,pair=namesp[j],r_2022=r[1],r_2025=r[2],change=r[2]-r[1])
    }
  };write_table(rbindlist(rows),paste0("correlations_",dom,if(use_pv)"" else "_paper_protocol"))
  implied<-list();coverage<-list()
  for(y in c(2022,2025)) {
    g<-d[wave==y];x<-g[complete.cases(g[,.(escs,hisei,paredint,homepos)])];w<-x$w_fstuwt
    X<-vapply(c("hisei","paredint","homepos"),function(v) zscore(x[[v]],w),numeric(nrow(x)))
    fit<-lm.wfit(cbind(1,X),x$escs,w);b<-fit$coefficients
    implied[[as.character(y)]]<-data.table(wave=y,hisei=b[2],pared=b[3],homepos=b[4],r2=1-wmean(fit$residuals^2,w)/wmean((x$escs-wmean(x$escs,w))^2,w),n=nrow(x))
    has<-g[is.finite(paredint)];lacks<-g[!is.finite(paredint)]
    r<-list(wave=y,coverage_pooled=100*wmean(as.numeric(is.finite(g$paredint)),g$w_fstuwt),coverage_mean_of_systems=100*mean(g[,.(v=wmean(as.numeric(is.finite(paredint)),w_fstuwt)),by=cnt]$v),pct_at_maximum_pooled=100*wmean(as.numeric(has$paredint==max(has$paredint)),has$w_fstuwt),hisei_if_pared_missing=wmean(lacks$hisei,lacks$w_fstuwt),hisei_if_pared_valid=wmean(has$hisei,has$w_fstuwt),score_if_pared_missing=wmean(lacks$score,lacks$w_fstuwt),score_if_pared_valid=wmean(has$score,has$w_fstuwt))
    bands<-cut(g$hisei,c(0,35,50,65,90),labels=c("<35","35-50","50-65","65+"))
    for(band in levels(bands)) {m<-which(bands==band);r[[paste0("pct_no_pared_hisei_",band)]]<-100*wmean(as.numeric(!is.finite(g$paredint[m])),g$w_fstuwt[m])}
    for(v in c("hisei","homepos","escs")) r[[paste0("coverage_",v,"_pooled")]]<-100*wmean(as.numeric(is.finite(g[[v]])),g$w_fstuwt)
    coverage[[as.character(y)]]<-as.data.table(r)
  }
  write_table(rbindlist(implied),"escs_implied_weights");write_table(rbindlist(coverage),paste0("pared_coverage_",dom))
}
