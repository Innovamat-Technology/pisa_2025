# Chapter 22, tables 22.A.16/.17 and the underlying STQ parameter worksheet.
# These are published parameters, not estimates fitted to the released scores.
technical_2025_parameters <- function() {
  path<-file.path(REFERENCE,"technical2025_ch22_tables.xlsx")
  d<-as.data.table(readxl::read_excel(path,"STQ",col_names=FALSE,.name_repair="minimal"))
  setnames(d,paste0("v",seq_len(ncol(d))));d<-d[v2=="HOMEPOS"]
  p<-data.table(parameter_id=d$v3,item=tolower(substr(d$v3,1,10)),slope=as.numeric(d$v4),location=as.numeric(d$v5))
  for(j in 1:5)set(p,j=paste0("step",j),value=as.numeric(d[[paste0("v",j+5)]]))
  p[,scope:=fifelse(grepl("_R$",parameter_id),"international",fifelse(grepl("_R[A-Z]{3}$",parameter_id),"national","released"))]
  p[,national_country:=fifelse(scope=="national",sub(".*_R","",parameter_id),NA_character_)]
  releases<-rbindlist(lapply(seq(11,27,2),function(j)data.table(parameter_id=d$v3,cnt=d[[j]],language=d[[j+1]])))
  releases<-unique(releases[!is.na(cnt)&!is.na(language)])
  releases[,language2:=sub("-.*","",language)]
  constants<-as.data.table(readxl::read_excel(path,"T22.A.2",skip=6,col_names=c("index","mean","sd")))
  constants<-constants[index=="HOMEPOS",.(mean=as.numeric(mean),sd=as.numeric(sd))]
  escs_constants<-as.data.table(readxl::read_excel(path,"T22.A.43",skip=6,col_names=c("component","mean","sd")))
  escs_constants<-escs_constants[component%in%c("HISEI","PAREDINT","HOMEPOS","Preliminary ESCS score")]
  escs_constants[,`:=`(mean=as.numeric(mean),sd=as.numeric(sd))]
  list(parameters=p,releases=releases,constants=constants,escs_constants=escs_constants)
}

official_2025_recodes <- function(d,items) {
  out<-matrix(NA_integer_,nrow(d),length(items),dimnames=list(NULL,items))
  for(j in seq_along(items)) {
    v<-items[j];raw<-if(v%in%c("st251q08ja","st251q09ja"))sub("q","d",v,fixed=TRUE) else v
    x<-d[[raw]]
    # Country adaptations are strings: six-digit adaptation code + response.
    if(v%in%c("st251q08ja","st251q09ja"))x<-suppressWarnings(as.numeric(substr(x,nchar(x),nchar(x))))
    if(grepl("^st250",v))z<-binary(x)
    else if(v=="st255q01ja")z<-pmax(0,recode_values(x,1:7)-2)
    else if(v=="st251q07ja")z<-as.integer(recode_values(x,1:4)>1)
    else if(v%in%c("st254q01ja","st254q04ja","st254q05ja"))z<-pmin(2,recode_values(x,1:4)-1)
    else z<-recode_values(x,1:4)-1
    out[,j]<-z
  }
  out[is.na(out)]<- -1L;storage.mode(out)<-"integer";out
}

official_2025_language <- function(x) {
  iso<-fread(file.path(REFERENCE,"iso_language_codes.csv"))
  out<-iso$alpha2[match(x,iso$alpha3)]
  aliases<-c(esp="es",slo="sk",val="ca",zhs="zh",mne="sr",ckb="ckb",kmr="kmr",kaa="kaa")
  hit<-x%in%names(aliases);out[hit]<-aliases[x[hit]]
  out
}

official_2025_group_parameters <- function(spec,country_code,language_code,region_code) {
  aliases<-c(QCI="CHN",QKO="KSV",QAZ="AZE",QUA="UKR")
  if(country_code%in%names(aliases))country_code<-unname(aliases[country_code])
  p<-copy(spec$parameters[scope=="international"])
  rel<-spec$releases[cnt==country_code & language2==language_code]
  if(nrow(rel)) {
    r<-spec$parameters[match(unique(rel$parameter_id),parameter_id)]
    stopifnot(!anyDuplicated(r$item));p<-rbind(p[!item%in%r$item],r)
  }
  nc<-country_code
  # The PUF's ST251D08JA adaptation prefix is 980000 in BOTH the French
  # and German-speaking Belgian communities (056000 in the Flemish one).
  if(country_code=="BEL")nc<-switch(region_code,`05601`="QBL",`05602`="QBR",`05603`="QBR",country_code)
  if(country_code=="GBR")nc<-if(region_code=="82604")"QSC" else "GBR"
  p<-rbind(p,spec$parameters[scope=="national"&national_country==nc])
  setorder(p,item);p
}

official_2025_model <- function(p) {
  # STQ contains ConQuest slopes and additive location/step coefficients:
  # log(P[k]/P[k-1]) = slope * theta - location - step[k].
  # Convert to the kernel's slope * (theta - threshold). Do NOT multiply
  # these slopes by 1.7 again, or interpret location as a classical threshold.
  a<-p$slope
  b<-lapply(seq_len(nrow(p)),function(j) {
    s<-as.numeric(p[j,paste0("step",1:5),with=FALSE]);s<-s[is.finite(s)]
    if(!length(s))s<-0
    (p$location[j]+s)/a[j]
  })
  list(a=a,b=b)
}

record_technical_2025_sources <- function() {
  files<-list.files(REFERENCE,pattern="^technical2025_",full.names=TRUE)
  manifest<-data.table(file=basename(files),sha256=vapply(files,digest::digest,character(1),algo="sha256",file=TRUE),bytes=file.info(files)$size,
    supplied_directory="/home/eudald/Baixades/PISA 2025 Technical Report",access_date="2026-09-23")
  fwrite(manifest,file.path(AUDIT,"technical2025_manifest.csv"))
  x<-as.data.table(readxl::read_excel(file.path(REFERENCE,"technical2025_ch13_tables.xlsx"),"T13.A.4",col_names=FALSE,.name_repair="minimal"))
  setnames(x,paste0("V",seq_len(ncol(x))))
  suppression<-list()
  for(i in seq(5,41,2)) {
    country<-x$V1[i]
    values<-as.character(unlist(x[i+1]));values<-values[!is.na(values)]
    variables<-trimws(unlist(strsplit(values,"[\r\n]+")))
    # Some Excel cells contain literal backslash-r/backslash-n text.
    variables<-trimws(unlist(strsplit(variables,"\\r\\n",fixed=TRUE)))
    variables<-variables[grepl("^ST25|LANGTEST|HISEI|HISCED|PARED|ESCS|HOMEPOS",variables)]
    if(length(variables))suppression[[country]]<-data.table(country=country,variable=variables,source="Table 13.A.4")
  }
  write_diagnostic(unique(rbindlist(suppression)),"official_2025_relevant_suppressions")
}

summarise_technical_2025 <- function() {
  rowsets<-list()
  for(entry in list(c("theta_quartiles","authors_original"),c("theta_official_recodes","official_recodes_pooled_fit"),c("theta_anchored_2025","fixed_2025_parameters"))) {
    th<-load_cache(entry[1])
    for(dom in DOMAINS)for(idx in intersect(names(th[[dom]]),c("escs","escs_h","escs_h_min3","homepos","homepos_h","escs_recodes3","escs_recodes10","homepos_recodes3","homepos_recodes10","escs_anchor25","homepos_anchor25"))) {
      T<-th[[dom]][[idx]]
      for(scope in c("OECD35","OECD34_without_NLD")) {
        countries<-setdiff(names(COUNTRY_NAMES),c("CRI","LUX","ESP",if(scope!="OECD35")"NLD"))
        stopifnot(all(countries%in%paired_countries(T)))
        a<-pool_theta(T[key(countries,2022)]);b<-pool_theta(T[key(countries,2025)])
        r<-change_row(a,b,idx,scope,length(countries),link_se(dom))
        r[,`:=`(domain=dom,calibration=entry[2])]
        rowsets[[length(rowsets)+1L]]<-r
      }
    }
  }
  write_table(rbindlist(rowsets,fill=TRUE),"technical_2025_gap_sensitivity")
  h<-read_diagnostic("official_2025_homepos_countries")
  cnts<-setdiff(names(COUNTRY_NAMES),c("CRI","LUX","ESP","NLD","NOR"))
  hh<-h[cnt%in%cnts]
  write_diagnostic(hh[,.(test="Official HOMEPOS from published rounded parameters, 33 OECD35 members",n_systems=.N,n=sum(n_compared),rmse=sqrt(sum(rmse^2*n_compared)/sum(n_compared)),max_abs_difference=max(max_abs_difference),missing_difference=sum(missing_difference),passed=all(max_abs_difference<.0005)&sum(missing_difference)==0)],"official_2025_scoring_validation")
  record_technical_2025_sources()
}

read_official_2025_raw <- function() {
  path<-file.path(CACHE,"technical2025/raw2025.rds")
  if(!file.exists(path)) {
    dir.create(dirname(path),recursive=TRUE,showWarnings=FALSE)
    vars<-c("cnt","cntstuid","oecd","langtest_qqq","subnatio","region","senwt","w_fstuwt","homepos","escs","hisei","paredint","hisced",COMMON,NAT,"st251d08ja","st251d09ja")
    d<-read_raw_columns(2025,vars)
    for(v in names(d))if(inherits(d[[v]],"haven_labelled"))set(d,j=v,value=haven::zap_labels(d[[v]]))
    saveRDS(d,path,compress=FALSE)
  }
  readRDS(path)
}

audit_official_2025 <- function() {
  spec<-technical_2025_parameters()
  write_diagnostic(spec$parameters,"official_2025_item_parameters")
  write_diagnostic(spec$releases,"official_2025_parameter_releases")
  write_diagnostic(spec$escs_constants,"official_2025_escs_constants")
  d<-read_official_2025_raw();d[,language2:=official_2025_language(langtest_qqq)]
  d[,`:=`(reconstructed_homepos=NA_real_,common_anchor25=NA_real_,n_items=0L)]
  groups<-d[,.(rows=list(.I)),by=.(cnt,language2,region)]
  diagnostics<-list()
  for(i in seq_len(nrow(groups))) {
    pos<-groups$rows[[i]];g<-d[pos]
    p<-official_2025_group_parameters(spec,g$cnt[1],g$language2[1],g$region[1])
    X<-official_2025_recodes(g,p$item);model<-official_2025_model(p)
    nobs<-rowSums(X>=0);valid<-nobs>=3
    scored<-resolve_wle(wle_cpp(X,model$a,model$b,min_items=3),X,model$a,model$b,bound=40)
    if(any(valid&(!scored$converged|scored$boundary))) {
      saveRDS(list(group=groups[i],X=X,model=model,scored=scored),file.path(CACHE,"technical2025/scoring_failure.rds"))
      stop("Official scoring failure: ",g$cnt[1]," / ",g$language2[1]," / ",g$region[1])
    }
    z<-(scored$theta-spec$constants$mean)/spec$constants$sd
    d[pos,`:=`(reconstructed_homepos=z,n_items=nobs)]
    keep<-p$item%in%COMMON
    cm<-resolve_wle(wle_cpp(X[,keep,drop=FALSE],model$a[keep],model$b[keep],min_items=3),X[,keep,drop=FALSE],model$a[keep],model$b[keep],bound=40)
    stopifnot(!any(rowSums(X[,keep,drop=FALSE]>=0)>=3&(!cm$converged|cm$boundary)))
    d[pos,common_anchor25:=(cm$theta-spec$constants$mean)/spec$constants$sd]
    delta<-z-g$homepos;ok<-is.finite(delta)
    diagnostics[[i]]<-data.table(cnt=g$cnt[1],language2=g$language2[1],region=g$region[1],n=nrow(g),n_compared=sum(ok),missing_difference=sum(is.na(z)!=is.na(g$homepos)),fallback_n=scored$fallback_n,rmse=if(any(ok))sqrt(mean(delta[ok]^2)) else NA_real_,max_abs_difference=if(any(ok))max(abs(delta[ok])) else NA_real_,n_difference_over_0001=sum(abs(delta[ok])>1e-4),released_items=sum(p$scope=="released"),national_items=sum(p$scope=="national"))
    if(i%%10==0){cat("Official scoring group",i,"/",nrow(groups),"\n");flush.console()}
  }
  write_diagnostic(rbindlist(diagnostics),"official_2025_homepos_groups")
  d[,homepos_delta:=reconstructed_homepos-homepos]
  country<-d[,.(n=.N,n_compared=sum(is.finite(homepos_delta)),n_missing_language_with_score=sum(is.na(language2)&is.finite(homepos)),missing_difference=sum(is.na(reconstructed_homepos)!=is.na(homepos)),rmse=if(any(is.finite(homepos_delta)))sqrt(mean(homepos_delta^2,na.rm=TRUE)) else NA_real_,max_abs_difference=if(any(is.finite(homepos_delta)))max(abs(homepos_delta),na.rm=TRUE) else NA_real_,n_difference_over_0001=sum(abs(homepos_delta)>1e-4,na.rm=TRUE)),by=.(cnt,oecd)]
  country[,status:=fifelse(n_compared==0,"no published scores",fifelse(rmse<1e-4,"matches within numerical/parameter precision","unresolved difference"))]
  country[cnt=="NLD",status:="PUF suppresses ST250Q10DA, ST251Q01JA, ST251Q04JA (13.A.4)"]
  country[cnt%in%c("NOR","LUX","MAC","QCY"),status:="PUF suppresses questionnaire language (13.A.4)"]
  write_diagnostic(country,"official_2025_homepos_countries")
  # The deterministic part of ESCS can be audited without reproducing random
  # regression residuals. Keep both the public PARED value and the annex value.
  constants<-spec$escs_constants
  component<-function(x,nm)(x-constants[component==nm,mean])/constants[component==nm,sd]
  composite<-function(h,p,ho) {
    initial<-(component(h,"HISEI")+component(p,"PAREDINT")+component(ho,"HOMEPOS"))/3
    component(initial,"Preliminary ESCS score")
  }
  for(mode in c("public_pared","annex_pared")) {
    pared<-d$paredint
    if(mode=="annex_pared")pared<-c(6,9,12,12,12,14.5,16,16,16)[d$hisced]
    z<-composite(d$hisei,pared,d$homepos)
    d[,escs_delta:=z-escs]
    tbl<-d[is.finite(escs_delta),.(n=.N,rmse=sqrt(mean(escs_delta^2)),max_abs_difference=max(abs(escs_delta)),n_difference_over_0001=sum(abs(escs_delta)>1e-4)),by=.(cnt,oecd)]
    tbl[,specification:=mode];write_diagnostic(tbl,paste0("official_2025_escs_",mode))
  }
  write_diagnostic(d[is.finite(hisced)&is.finite(paredint),.(n=.N),by=.(hisced,paredint)][,annex_years:=c(6,9,12,12,12,14.5,16,16,16)[hisced]],"official_2025_pared_discrepancy")
  write_diagnostic(d[,.(n=.N,senwt_sum=sum(senwt),max_abs_recomputed_senwt=max(abs(senwt-w_fstuwt/sum(w_fstuwt)*5000))),by=.(cnt,oecd)],"official_2025_calibration_population")
  save_cache(d[,.(cnt,cntstuid,oecd,langtest_qqq,language2,region,homepos,escs,hisei,paredint,hisced,reconstructed_homepos,common_anchor25,n_items)],"official_2025_scores")
  invisible(country)
}

# Controlled sensitivity: retain the authors' pooled calibration population and
# model, but use the official 2025 item recodes and score eligibility. This is
# deliberately NOT labeled an OECD calibration or a new official trend index.
build_official_recode_sensitivity <- function() {
  fields<-c("cnt","cntstuid","wave","w_fstuwt","hisei","paredint",COMMON,allpv)
  parts<-lapply(c(2022,2025),read_extract,cols=fields)
  common_countries<-intersect(parts[[1]]$cnt,parts[[2]]$cnt)
  d<-rbindlist(parts,fill=TRUE);rm(parts);d<-d[cnt%in%common_countries]
  X<-official_2025_recodes(d,COMMON)
  X[X<0]<-NA_integer_
  cal<-cbind(d[,.(cnt,wave,w_fstuwt)],as.data.table(X))
  # Only the item matrix uses -1 for missing; identifiers and weights are intact.
  ir<-fit_and_score(cal,COMMON,10,"irt16_oecd_recodes");rm(cal,X);gc(FALSE)
  d[,`:=`(homepos_recodes3=ir$score3,homepos_recodes10=ir$score)]
  d<-d[cnt!="CRI"];w<-senate(d)
  d[,pared_common:=fifelse(paredint==3,6,fifelse(paredint==14.5,14,paredint))]
  for(n in c(3,10)) {
    v<-paste0("homepos_recodes",n)
    sc<-escs(cbind(d$hisei,d$pared_common,d[[v]]),cell_id(d),w)
    set(d,j=paste0("escs_recodes",n),value=sc$score)
  }
  save_cache(d,"analysis_official_recodes")
  th<-collect_theta(d,c("homepos_recodes3","homepos_recodes10","escs_recodes3","escs_recodes10"))
  save_cache(th,"theta_official_recodes");quartile_tables(th,"_official_recodes")
  invisible(d)
}

# A second sensitivity uses the actual 2025 country/language item parameters
# on the common item set in BOTH cycles. This fixes the metric by construction;
# it does not establish invariance of 2025 parameters in 2022.
build_anchored_2025_sensitivity <- function() {
  d<-load_cache("analysis_official_recodes")
  spec<-technical_2025_parameters()
  raw_language<-read_raw_columns(2022,c("cnt","cntstuid","langtest_qqq"))
  labels<-attr(raw_language$langtest_qqq,"labels")
  wanted<-c(Spanish="es",Italian="it",Japanese="ja",Korean="ko",Basque="eu")
  codes<-labels[match(names(wanted),names(labels))]
  stopifnot(!anyNA(codes))
  raw_language[,language2:=unname(wanted[match(as.numeric(langtest_qqq),as.numeric(codes))])]
  # Only these five languages have releases among the 16 common items in OECD
  # countries in the analysis. Others use the published international values.
  relevant<-spec$releases[parameter_id%in%spec$parameters[item%in%COMMON,parameter_id]&cnt%in%unique(d$cnt)]
  stopifnot(all(unique(relevant$language2)%in%wanted))
  d[,homepos_anchor25:=NA_real_]
  old<-which(d$wave==2022)
  pos<-match(paste(d$cnt[old],d$cntstuid[old]),paste(raw_language$cnt,raw_language$cntstuid))
  stopifnot(!anyNA(pos))
  d[old,language2:=raw_language$language2[pos]];rm(raw_language);gc(FALSE)
  groups<-d[wave==2022,.(rows=list(.I)),by=.(cnt,language2)]
  for(i in seq_len(nrow(groups))) {
    ix<-groups$rows[[i]];g<-d[ix]
    p<-official_2025_group_parameters(spec,g$cnt[1],g$language2[1],"")[item%in%COMMON]
    X<-official_2025_recodes(g,p$item);m<-official_2025_model(p)
    s<-resolve_wle(wle_cpp(X,m$a,m$b,3),X,m$a,m$b,bound=40)
    stopifnot(!any(rowSums(X>=0)>=3&(!s$converged|s$boundary)))
    d[ix,homepos_anchor25:=(s$theta-spec$constants$mean)/spec$constants$sd]
  }
  reference<-load_cache("official_2025_scores")
  recent<-which(d$wave==2025)
  pos<-match(paste(d$cnt[recent],d$cntstuid[recent]),paste(reference$cnt,reference$cntstuid))
  stopifnot(!anyNA(pos));d[recent,homepos_anchor25:=reference$common_anchor25[pos]]
  d[,escs_anchor25:=escs(cbind(hisei,pared_common,homepos_anchor25),cell_id(d),senate(d))$score]
  save_cache(d[,.(cnt,cntstuid,wave,homepos_anchor25,escs_anchor25)],"anchored_2025_indices")
  th<-collect_theta(d,c("homepos_anchor25","escs_anchor25"))
  save_cache(th,"theta_anchored_2025");quartile_tables(th,"_anchored_2025")
  invisible(NULL)
}
