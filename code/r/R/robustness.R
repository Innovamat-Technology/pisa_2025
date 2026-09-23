composite_variants <- function(d) {
  w<-senate(d);group<-cell_id(d);RAW<-as.matrix(d[,.(hisei,pared_c,homepos_irt)])
  X<-as.matrix(d[,.(hisei_h,pared_h,homepos_h)]);V<-list()
  V[["1. OECD rule: equal-weighted mean, regression imputation (the paper's composite)"]]<-escs(RAW,group,w)$score
  V[["2. OECD rule, mean of the available components"]]<-escs(RAW,group,w,imputation="mean")$score
  V[["3. OECD rule, complete cases only"]]<-escs(RAW,group,w,imputation="complete")$score
  V[["4. OECD rule, imputation without the random residual"]]<-escs(RAW,group,w,noise=FALSE)$score
  s<-rep(NA_real_,nrow(d))
  for(y in c(2022,2025)) {m<-d$wave==y;s[m]<-escs(RAW[m,],group[m],w[m])$score}
  V[["5. OECD rule, metric re-anchored in each cycle"]]<-s
  Xp<-apply(X,2,zscore,w=w);V[["6. First principal component, pooled standardization"]]<-pca_score(Xp,w)$score
  s<-rep(NA_real_,nrow(d));t<-s;vs<-list()
  for(y in c(2022,2025)) {
    m<-d$wave==y;Z<-apply(X,2,zscore,w=w,mask=m);s[m]<-pca_score(Z,w,m)$score[m]
    p<-pca_score(Xp,w,m);t[m]<-p$score[m];vs[[as.character(y)]]<-p$loadings
  }
  V[["7. Per-cycle standardization, per-cycle principal component"]]<-s
  V[["8. Pooled standardization, per-cycle principal component"]]<-t
  Xi<-Xp;Xi[!is.finite(Xi)]<-0;nv<-rowSums(is.finite(Xp))
  for(y in c(2022,2025)) {s<-drop(Xi%*%vs[[as.character(y)]]);s[nv<2]<-NA_real_;V[[paste0(if(y==2022)"9. " else "10. ",y," principal-component weights in both cycles")]]<-s}
  V
}
run_composites <- function(d) {
  V<-composite_variants(d);d<-copy(d);cols<-paste0("variant",1:10)
  for(i in seq_along(V)) set(d,j=cols[i],value=V[[i]])
  TH<-collect_theta(d,cols)
  for(dom in DOMAINS) {
    rows<-list()
    for(i in seq_along(V)) {
      T<-TH[[dom]][[cols[i]]];cs<-paired_countries(T)
      a<-pool_theta(T[key(cs,2022)]);b<-pool_theta(T[key(cs,2025)])
      ca<-contrast(a,c(-1,0,0,1));cb<-contrast(b,c(-1,0,0,1))
      rows[[i]]<-data.table(construction=names(V)[i],Q1_change=b$estimate[1]-a$estimate[1],Q4_change=b$estimate[4]-a$estimate[4],gap_change=cb[1]-ca[1],se=sqrt(ca[2]^2+cb[2]^2),coverage=100*mean(is.finite(V[[i]])),n_systems=length(cs))
    };write_table(rbindlist(rows),paste0("composite_weights_",dom))
  }
}
run_fixed <- function(d) {
  cuts<-quantile(d$cpos,c(.25,.75),na.rm=TRUE)
  GROUPS<-list("Parents with tertiary education (16 years)"=function(g)g$paredint>=16,"Parents with 12 years or fewer"=function(g)g$paredint<=12,"HISEI >= 60"=function(g)g$hisei>=60,"HISEI < 35"=function(g)g$hisei<35,"More than 100 books"=function(g)g$books7>=5,"25 books or fewer"=function(g)g$books7<=3,"No valid ESCS"=function(g)!is.finite(g$escs),"Valid ESCS"=function(g)is.finite(g$escs))
  BASE<-c("paredint","paredint","hisei","hisei","books7","books7",NA,NA)
  RULES<-list("Occupation: HISEI >= 60 vs < 35"=list(function(g)g$hisei>=60,function(g)g$hisei<35),"Education: tertiary vs 12 years or fewer"=list(function(g)g$paredint>=16,function(g)g$paredint<=12),"Books: more than 100 vs 25 or fewer"=list(function(g)g$books7>=5,function(g)g$books7<=3),"Possessions: top vs bottom quartile of the fixed 16-item score"=list(function(g)g$cpos>=cuts[2],function(g)g$cpos<=cuts[1]),"Occupation and books"=list(function(g)g$hisei>=60&g$books7>=5,function(g)g$hisei<35&g$books7<=3),"Occupation, education and books"=list(function(g)g$hisei>=60&g$paredint>=16&g$books7>=5,function(g)g$hisei<35&g$paredint<=12&g$books7<=3))
  TH<-TR<-setNames(vector("list",3),DOMAINS); shares<-list();i<-0L
  cells<-d[,.(rows=list(.I)),by=.(cnt,wave)][order(cnt,wave)]
  for(ci in seq_len(nrow(cells))) {
    g<-d[cells$rows[[ci]]];W<-weights_for(g);ky<-key(g$cnt[1],g$wave[1])
    for(j in seq_along(GROUPS)) {
      s<-GROUPS[[j]](g);s[is.na(s)]<-FALSE;base<-if(is.na(BASE[j])) rep(TRUE,nrow(g)) else is.finite(g[[BASE[j]]])
      i<-i+1L;shares[[i]]<-data.table(cnt=g$cnt[1],wave=g$wave[1],group=names(GROUPS)[j],pct=100*wmean(as.numeric(s[base]),g$w_fstuwt[base]))
      for(dom in DOMAINS) {P<-as.matrix(g[,pvcols(dom),with=FALSE]);m<-s&complete.cases(P);if(sum(m)>=30)TH[[dom]][[names(GROUPS)[j]]][[ky]]<-theta_groups(rep(0,sum(m)),W[m,,drop=FALSE],P[m,,drop=FALSE],1)}
    }
    for(nm in names(RULES)) {
      top<-RULES[[nm]][[1]](g);bottom<-RULES[[nm]][[2]](g);top[is.na(top)]<-FALSE;bottom[is.na(bottom)]<-FALSE
      code<-ifelse(top,1L,ifelse(bottom,0L,-1L))
      for(dom in DOMAINS) {P<-as.matrix(g[,pvcols(dom),with=FALSE]);m<-code>=0&complete.cases(P);if(sum(code[m]==0)>=30&&sum(code[m]==1)>=30)TR[[dom]][[nm]][[ky]]<-theta_groups(code[m],W[m,,drop=FALSE],P[m,,drop=FALSE],2)}
    }
  }
  shares<-rbindlist(shares);write_table(shares,"fixed_group_shares_by_system")
  for(dom in DOMAINS) {
    rows<-list()
    for(nm in names(GROUPS)) {
      T<-TH[[dom]][[nm]];cs<-setdiff(paired_countries(T),"CRI");a<-pool_theta(T[key(cs,2022)]);b<-pool_theta(T[key(cs,2025)])
      sh<-shares[group==nm & cnt%in%cs,.(pct=mean(pct)),by=wave]
      rows[[nm]]<-data.table(group=nm,n_systems=length(cs),pct_2022=sh[wave==2022,pct],pct_2025=sh[wave==2025,pct],mean_2022=a$estimate,mean_2025=b$estimate,change=b$estimate-a$estimate,se=sqrt(a$se^2+b$se^2+link_se(dom)^2))
    };write_table(rbindlist(rows),paste0("fixed_groups_",dom))
    rows<-list();per<-list();i<-j<-0L
    for(nm in names(RULES)) {
      T<-TR[[dom]][[nm]];cs0<-paired_countries(T)
      for(incl in c(FALSE,TRUE)) {
        cs<-if(incl)cs0 else setdiff(cs0,"CRI");if(incl&&!"CRI"%in%cs)next
        changes<-numeric()
        for(cnt in cs) {
          a<-contrast(summarise_theta(T[[key(cnt,2022)]]),c(-1,1));b<-contrast(summarise_theta(T[[key(cnt,2025)]]),c(-1,1));changes<-c(changes,b[1]-a[1])
          if(!incl){j<-j+1L;per[[j]]<-data.table(rule=nm,cnt=cnt,gap_2022=a[1],gap_2025=b[1],change=b[1]-a[1],se=sqrt(a[2]^2+b[2]^2))}
        }
        a<-contrast(pool_theta(T[key(cs,2022)]),c(-1,1));b<-contrast(pool_theta(T[key(cs,2025)]),c(-1,1))
        i<-i+1L;rows[[i]]<-data.table(rule=paste0(nm,if(incl)" (with CRI)" else ""),n_systems=length(cs),gap_2022=a[1],gap_2025=b[1],change=b[1]-a[1],se=sqrt(a[2]^2+b[2]^2),narrows_in=sum(changes<0))
      }
    }
    write_table(rbindlist(rows),paste0("fixed_rules_",dom));write_table(rbindlist(per),paste0("fixed_rules_by_system_",dom))
  }
}
run_systems <- function(d) {
  for(dom in DOMAINS) {
    q<-read_table(paste0("quartiles_",dom));q<-q[!cnt%in%c("OECD","OECD35")]
    cols<-c("Q1_change","Q4_change","Q4-Q1_change","Q4-Q1_se");out<-data.table(cnt=sort(unique(q$cnt)))
    for(idx in c("escs","escs_h","homepos","homepos_h"))for(v in cols)out[,(paste(idx,v,sep="_")):=q[index==idx][match(out$cnt,cnt),get(v)]]
    setorderv(out,"escs_Q4-Q1_change");write_table(out,paste0("systems_q1_q4_",dom))
    s<-d[wave==2022,.(mean_score_2022=wmean(rowMeans(.SD),w_fstuwt),mean_escs_2022=wmean(escs,w_fstuwt)),by=cnt,.SDcols=pvcols(dom)]
    gdp<-fread(file.path(ROOT,"reference/gdp_per_capita_ppp_2022.csv"));s[,log_gdp_pc:=log(gdp$gdp_pc_ppp_2022[match(cnt,gdp$cnt)])]
    s[,published:=q[index=="escs"][match(s$cnt,cnt),get("Q4-Q1_change")]];s[,harmonized:=q[index=="escs_h"][match(s$cnt,cnt),get("Q4-Q1_change")]];s[,mismatch:=published-harmonized]
    write_table(s,paste0("systems_income_",dom));r<-cor(as.matrix(s[,-"cnt"]),use="pairwise.complete.obs")
    write_table(data.table(index=c("mismatch","published","harmonized"),r[c("mismatch","published","harmonized"),c("log_gdp_pc","mean_score_2022","mean_escs_2022")]),paste0("systems_correlations_",dom))
  }
}
