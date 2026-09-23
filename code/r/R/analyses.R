COUNTRY_NAMES <- c(AUS="Australia",AUT="Austria",BEL="Belgium",CAN="Canada",CHE="Switzerland",CHL="Chile",COL="Colombia",CRI="Costa Rica",CZE="Czechia",DEU="Germany",DNK="Denmark",ESP="Spain",EST="Estonia",FIN="Finland",FRA="France",GBR="United Kingdom",GRC="Greece",HUN="Hungary",IRL="Ireland",ISL="Iceland",ISR="Israel",ITA="Italy",JPN="Japan",KOR="Korea",LTU="Lithuania",LUX="Luxembourg",LVA="Latvia",MEX="Mexico",NLD="Netherlands",NOR="Norway",NZL="New Zealand",POL="Poland",PRT="Portugal",SVK="Slovak Republic",SVN="Slovenia",SWE="Sweden",TUR="Türkiye",USA="United States")

prepare_reference <- function() {
  path<-file.path(REFERENCE,"oecd_2025_equity.xlsx")
  if(!file.exists(path)) download.file("https://stat.link/k68msa",path,mode="wb")
  out<-list(); changes<-list(); errors<-list();count<-0L
  for(dom in DOMAINS) for(idx in c("escs","homepos")) {
    number<-c(scie=22,read=23,math=24)[[dom]]+if(idx=="homepos")14 else 0
    sheet<-paste0("Table I.B1.2b.",number)
    x<-as.data.frame(readxl::read_excel(path,sheet=sheet,col_names=FALSE,.name_repair="unique_quiet"))
    namesx<-trimws(gsub("*","",as.character(x[[1]]),fixed=TRUE))
    namesx[namesx=="Czech Republic"]<-"Czechia"
    for(cnt in c(names(COUNTRY_NAMES),"OECD35","OECD23")) {
      label<-if(cnt=="OECD35") "OECD average-35" else if(cnt=="OECD23") "OECD average-23" else COUNTRY_NAMES[[cnt]]
      row<-which(namesx==label);if(length(row)!=1) next
      nums<-suppressWarnings(as.numeric(x[row,-1]))
      for(j in 1:4) for(q in 1:5) {
        value<-nums[(j-1)*10+(q-1)*2+1];se<-nums[(j-1)*10+(q-1)*2+2]
        count<-count+1L;out[[count]]<-data.table(cnt=cnt,domain=dom,index=idx,wave=c(2015,2018,2022,2025)[j],group=if(q==5) "Q4-Q1" else paste0("Q",q),estimate=value,se=se,table=sheet)
      }
      for(q in 1:5) changes[[length(changes)+1L]]<-data.table(cnt=cnt,domain=dom,index=idx,group=if(q==5)"Q4-Q1" else paste0("Q",q),estimate=nums[61+(q-1)*2],se=nums[62+(q-1)*2],table=sheet)
      if(cnt=="OECD35" && idx=="escs") {
        vlink<-nums[c(62,64,66,68)]^2-nums[c(22,24,26,28)]^2-nums[c(32,34,36,38)]^2
        errors[[dom]]<-data.table(domain=dom,link_se_2022_2025=sqrt(median(vlink)),spread_of_implied_variances=diff(range(vlink)),source=sheet,method="Recovered from published SE(change)^2 - SE(2022)^2 - SE(2025)^2; rounded published inputs")
      }
    }
  }
  write_reference_table(rbindlist(out),"official_reference");write_reference_table(rbindlist(changes),"official_reference_changes");write_reference_table(rbindlist(errors),"link_errors")
}
link_se <- function(dom) read_reference_table("link_errors")[domain==dom,link_se_2022_2025]
key <- function(cnt,wave) paste(cnt,wave,sep="/")
collect_theta <- function(d,indices,k=4,mode="replicate",min_n=200,check=FALSE) {
  TH<-setNames(lapply(DOMAINS,function(z) setNames(vector("list",length(indices)),indices)),DOMAINS); checks<-list();i<-0L
  groups<-d[,.(rows=list(.I)),by=.(cnt,wave)][order(cnt,wave)]
  for(gi in seq_len(nrow(groups))) {
    pos<-groups$rows[[gi]];g<-d[pos];W<-weights_for(g);ky<-key(g$cnt[1],g$wave[1]);code_cache<-list()
    for(dom in DOMAINS) {
      P<-as.matrix(g[,pvcols(dom),with=FALSE]);ok<-rowSums(is.finite(P))==10
      for(idx in indices) {
        v<-sub("_cc$","",idx);m<-ok & is.finite(g[[v]])
        if(grepl("_cc$",idx)) m<-m & complete.cases(g[,.(escs,hisei,paredint,homepos,homepos_h)])
        if(sum(m)<min_n) next
        base<-if(mode=="fixed"&&!grepl("_cc$",idx)) is.finite(g[[v]]) else m
        cached<-code_cache[[idx]]
        if(!is.null(cached)&&identical(cached$mask,m))code<-cached$code else {
          code<-quantile_codes(g[[v]][base],W[base,,drop=FALSE],k,mode)
          code<-code[m[base],,drop=FALSE]
          code_cache[[idx]]<-list(mask=m,code=code)
        }
        TH[[dom]][[idx]][[ky]]<-group_means_cpp(code,W[m,,drop=FALSE],P[m,,drop=FALSE],k)
        if(check) {
          i<-i+1L;r<-list(cnt=g$cnt[1],wave=g$wave[1],index=idx,domain=dom,n=sum(m))
          for(q in 1:k) {r[[paste0("weight_Q",q)]]<-sum(W[m,1][code[,1]==q-1])/sum(W[m,1])*100;r[[paste0("n_Q",q)]]<-sum(code[,1]==q-1)}
          checks[[i]]<-as.data.table(r)
        }
      }
    }
    cat("Groups:",mode,k,ky,"\n");flush.console()
  }
  if(check) {ct<-rbindlist(checks);for(dom in DOMAINS) write_table(ct[domain==dom],paste0("quartile_check_",dom,if(mode=="paper")"_paper_protocol" else ""))}
  TH
}
paired_countries <- function(T,years=c(2022,2025)) {
  Reduce(intersect,lapply(years,function(y) sub(paste0("/",y,"$"),"",grep(paste0("/",y,"$"),names(T),value=TRUE))))
}
change_row <- function(a,b,idx,cnt,n,link=0) {
  r<-list(index=idx,cnt=cnt,n_systems=n)
  for(q in 1:length(a$estimate)) {
    nm<-paste0("Q",q);r[[paste0(nm,"_2022")]]<-a$estimate[q];r[[paste0(nm,"_2025")]]<-b$estimate[q]
    r[[paste0(nm,"_change")]]<-b$estimate[q]-a$estimate[q];r[[paste0(nm,"_se")]]<-sqrt(a$se[q]^2+b$se[q]^2+link^2)
  }
  for(pair in combn(seq_along(a$estimate),2,simplify=FALSE)) {
    c<-rep(0,length(a$estimate));c[pair]<-c(-1,1);x<-contrast(a,c);y<-contrast(b,c)
    nm<-paste0("Q",pair[2],"-Q",pair[1]);r[[paste0(nm,"_2022")]]<-x[1];r[[paste0(nm,"_2025")]]<-y[1]
    r[[paste0(nm,"_change")]]<-y[1]-x[1];r[[paste0(nm,"_se")]]<-sqrt(x[2]^2+y[2]^2)
  }
  as.data.table(r)
}
quartile_tables <- function(TH,suffix="",pool_method="independent") {
  for(dom in DOMAINS) {
    rows<-list();i<-0L
    for(idx in names(TH[[dom]])) {
      T<-TH[[dom]][[idx]];cnts<-sort(paired_countries(T));if(!length(cnts)) next
      for(cnt in c(cnts,"OECD","OECD35")) {
        use<-if(cnt=="OECD") cnts else if(cnt=="OECD35") intersect(cnts,setdiff(names(COUNTRY_NAMES),c("CRI","LUX","ESP"))) else cnt
        if(!length(use)) next
        a<-pool_theta(T[key(use,2022)],pool_method);b<-pool_theta(T[key(use,2025)],pool_method)
        i<-i+1L;rows[[i]]<-change_row(a,b,idx,cnt,if(cnt%in%c("OECD","OECD35"))length(use) else length(cnts),if(pool_method=="paper")0 else link_se(dom))
      }
    }
    write_table(rbindlist(rows,fill=TRUE),paste0("quartiles_",dom,suffix))
  }
}
run_quartiles <- function(d) {
  indices<-c("escs","escs_h","escs_pca","hisei_h","pared_h","homepos","homepos_h","books_h","escs_cc","escs_h_cc","escs_h_min3")
  th<-collect_theta(d,indices,check=TRUE);save_cache(th,"theta_quartiles");quartile_tables(th)
  save_cache(th,"theta_quartiles_paper");quartile_tables(th,"_paper_protocol","paper")
  for(dom in DOMAINS) write_table(read_table(paste0("quartile_check_",dom)),paste0("quartile_check_",dom,"_paper_protocol"))
  fixed<-collect_theta(d,indices,mode="fixed");save_cache(fixed,"theta_quartiles_fixed");quartile_tables(fixed,"_fixed_quartiles")
  run_deciles(d)
}
run_deciles <- function(d) {
  th10<-collect_theta(d,c("escs","escs_h","escs_pca","homepos","homepos_h"),k=10,min_n=400)
  for(dom in DOMAINS) {
    rows<-list();i<-0L
    for(idx in names(th10[[dom]])) {
      T<-th10[[dom]][[idx]];cnts<-sort(paired_countries(T));a<-pool_theta(T[key(cnts,2022)]);b<-pool_theta(T[key(cnts,2025)])
      for(k in 1:11) {
        if(k<=10) {x<-c(a$estimate[k],a$se[k]);y<-c(b$estimate[k],b$se[k]);lk<-link_se(dom)}
        else {x<-contrast(a,c(-1,rep(0,8),1));y<-contrast(b,c(-1,rep(0,8),1));lk<-0}
        i<-i+1L;rows[[i]]<-data.table(index=idx,decile=if(k<=10)as.character(k) else "D10-D1",n_systems=length(cnts),mean_2022=x[1],mean_2025=y[1],change=y[1]-x[1],se=sqrt(x[2]^2+y[2]^2+lk^2))
      }
    };write_table(rbindlist(rows),paste0("deciles_",dom))
  }
}
run_series <- function(d,scope="paper") {
  labels<-c(escs="ESCS, published",escs_h4="ESCS, harmonized (four cycles)",escs_mean4="ESCS, harmonized (four cycles), no imputation",escs_pca4="ESCS, harmonized (four cycles), principal component",homepos="HOMEPOS, published",homepos_h4="HOMEPOS, harmonized (four cycles)",hisei="HISEI",pared_c="PARED (common scale)",books="Books at home (six categories)")
  if(scope=="oecd35")labels<-c(labels,escs_trend2022="ESCS, official OECD 2022 trend rescaling",homepos_trend2022="HOMEPOS, official OECD 2022 trend rescaling")
  th<-collect_theta(d,names(labels));save_cache(th,if(scope=="paper")"theta_series" else "theta_series_oecd35")
  for(dom in DOMAINS) {
    rows<-list();official<-list()
    for(idx in names(labels)) {
      T<-th[[dom]][[idx]];cnts<-sort(paired_countries(T,c(2015,2018,2022,2025)))
      for(set in "sample") {
        use<-cnts
        r<-list(index=idx,label=labels[[idx]],n_systems=length(use))
        for(y in c(2015,2018,2022,2025)) {s<-contrast(pool_theta(T[key(use,y)]),c(-1,0,0,1));r[[paste0("y",y)]]<-s[1];r[[paste0("se",y)]]<-s[2]}
        rows[[idx]]<-as.data.table(r)
      }
    }
    write_table(rbindlist(rows),paste0("gap_series_",dom,if(scope=="paper")"" else "_oecd35"))
  }
}

run_reclassification <- function(d) {
  d<-copy(d[is.finite(homepos)&is.finite(homepos_h)]);d[,`:=`(q_pub=0L,q_har=0L)]
  d[,q_pub:=quantile_codes(homepos,matrix(w_fstuwt))[,1]+1L,by=.(cnt,wave)]
  d[,q_har:=quantile_codes(homepos_h,matrix(w_fstuwt))[,1]+1L,by=.(cnt,wave)]
  by_country<-function(g,f) mean(vapply(split(g,by="cnt"),f,numeric(1)),na.rm=TRUE)
  rows<-list();profiles<-list();levels<-list();i<-0L
  for(y in c(2022,2025)) {
    g<-d[wave==y]
    rows[[as.character(y)]]<-data.table(wave=y,
      change_quartile_pct=100*by_country(g,function(x) wmean(as.numeric(x$q_pub!=x$q_har),x$w_fstuwt)),
      pubQ4_still_Q4_pct=100*by_country(g[q_pub==4],function(x) wmean(as.numeric(x$q_har==4),x$w_fstuwt)),
      pubQ1_still_Q1_pct=100*by_country(g[q_pub==1],function(x) wmean(as.numeric(x$q_har==1),x$w_fstuwt)),
      r_within_country_unweighted=by_country(g,function(x) cor(x$homepos,x$homepos_h)),
      r_within_country_weighted=by_country(g,function(x) wcorr(x$homepos,x$homepos_h,x$w_fstuwt)))
    groups<-list("In Q4 under both"=g$q_pub==4&g$q_har==4,"Published Q4, not harmonized Q4"=g$q_pub==4&g$q_har!=4,"Harmonized Q4, not published Q4"=g$q_pub!=4&g$q_har==4,"In Q1 under both"=g$q_pub==1&g$q_har==1,"Published Q1, not harmonized Q1"=g$q_pub==1&g$q_har!=1,"Harmonized Q1, not published Q1"=g$q_pub!=1&g$q_har==1)
    for(nm in names(groups)) {
      x<-g[groups[[nm]]];r<-list(wave=y,group=nm,pct_students=100*sum(x$w_fstuwt)/sum(g$w_fstuwt))
      for(v in c("math","hisei","paredint","books7","n_booktypes","n_national_yes","n_national_adm")) r[[v]]<-wmean(x[[v]],x$w_fstuwt)
      i<-i+1L;profiles[[i]]<-as.data.table(r)
    }
    ct<-g[,.(pct=100*sum(w_fstuwt)/sum(g$w_fstuwt)),by=.(q_pub,q_har)]
    write_table(dcast(ct,q_pub~q_har,value.var="pct"),paste0("transition_matrix_",y))
    for(v in c("q_pub","q_har")) levels[[paste(v,y)]]<-by_country(g,function(x) wmean(x$math[x[[v]]==4],x$w_fstuwt[x[[v]]==4])-wmean(x$math[x[[v]]==1],x$w_fstuwt[x[[v]]==1]))
  }
  write_table(rbindlist(rows),"table3_reclassification");write_table(rbindlist(profiles),"table4_mover_profiles")
  r<-rbindlist(lapply(c("q_pub","q_har"),function(v) data.table(index=if(v=="q_pub")"HOMEPOS published" else "HOMEPOS harmonized",gap_2022=levels[[paste(v,2022)]],gap_2025=levels[[paste(v,2025)]])))
  r[,change:=gap_2025-gap_2022];write_table(r,"gap_levels_homepos")
}
