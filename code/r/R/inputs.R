raw_path <- function(year) {
  names<-c(`2015`="CY6_MS_CMB_STU_QQQ.sav",`2018`="CY07_MSU_STU_QQQ.sav",`2022`="CY08MSP_STU_QQQ.SAV",`2025`="CY09_MS_STU_PUF.sav")
  p<-file.path(Sys.getenv("PISA_RAW_DIR",file.path(ROOT,"data/raw")),names[[as.character(year)]])
  if(!file.exists(p))stop("Raw SPSS file required for missing 2015 countries: ",p)
  p
}
read_raw_columns <- function(year,cols) {
  path<-raw_path(year);actual<-names(haven::read_sav(path,n_max=0))
  selected<-actual[match(toupper(cols),toupper(actual))]
  if(anyNA(selected))stop("Missing raw variables: ",paste(cols[is.na(selected)],collapse=", "))
  g<-as.data.table(haven::read_sav(path,col_select=tidyselect::all_of(selected),user_na=FALSE))
  setnames(g,tolower(names(g)));g
}
supplement_2015 <- function() {
  if(file.exists(file.path(CACHE,"students_supplement_2015.rds")))return(invisible(NULL))
  olditems<-c(sprintf("ST011Q%02dTA",1:12),"ST011Q16NA","ST012Q01TA","ST012Q02TA","ST012Q03TA",sprintf("ST012Q%02dNA",5:9),"ST013Q01TA")
  cols<-c("CNT","CNTSCHID","CNTSTUID","W_FSTUWT","ESCS","HOMEPOS","HISEI","HISCED",toupper(allpv),olditems,paste0("W_FSTURWT",1:80))
  g<-read_raw_columns(2015,cols);g<-g[cnt%in%c("COL","LTU")];gc(FALSE)
  stopifnot(setequal(unique(g$cnt),c("COL","LTU")))
  wnames<-paste0("w_fsturwt",1:80);W<-as.matrix(g[,..wnames]);storage.mode(W)<-"double"
  saveRDS(W,file.path(CACHE,"weights_supplement_2015.rds"),compress=FALSE);g[,(wnames):=NULL]
  setnames(g,"st013q01ta","books6");g[,`:=`(wave=2015L,raw_row=seq_len(.N),supplement=TRUE,paredint=NA_real_,cntstuid=as.character(cntstuid),cntschid=as.character(cntschid))]
  for(v in names(g)) if(inherits(g[[v]],"haven_labelled")) set(g,j=v,value=haven::zap_labels(g[[v]]))
  saveRDS(g,file.path(CACHE,"students_supplement_2015.rds"),compress=FALSE)
  write_diagnostic(g[,.(n=.N),by=.(wave,cnt)],"restored_2015_countries")
}
prepare_trend_indices <- function() {
  z<-file.path(CACHE,"escs_trend.zip");csv<-file.path(CACHE,"escs_trend.csv")
  if(!file.exists(z))download.file("https://webfs.oecd.org/pisa2022/escs_trend.zip",z,mode="wb")
  if(!file.exists(csv))unzip(z,exdir=CACHE)
  t<-fread(csv);t<-t[cycle%in%c(6,7)&cnt%in%names(COUNTRY_NAMES)]
  t[,`:=`(wave=fifelse(cycle==6,2015L,2018L),cntstuid=as.character(studentid))]
  stopifnot(!anyDuplicated(t[,.(wave,cnt,cntstuid)]))
  saveRDS(t[,.(wave,cnt,cntstuid,escs_trend2022=escs_trend,homepos_trend2022=homepos_trend,hisei_trend2022=hisei_trend,pared_trend2022=paredint_trend)],file.path(CACHE,"official_trend_indices.rds"),compress=FALSE)
}
