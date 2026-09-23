# Run from the repository root: Rscript code/r/step.R <stage> [scope].
args <- commandArgs(trailingOnly=TRUE)
if(!length(args)) stop("Usage: Rscript code/r/step.R <stage> [paper|oecd35|summary]")
step <- as.integer(args[1])
stopifnot(length(args)<=2, !is.na(step), step%in%c(1L,2L,5:13,15L))
source(file.path(Sys.getenv("PISA_REPO","."),"code/r/R/core.R"))
for(f in c("irt","analyses","descriptive","robustness","inputs")) source(file.path(RR,"R",paste0(f,".R")))
cat("R step",step,"started",format(Sys.time()),"\n")
if(step==1){prepare_reference();supplement_2015();prepare_trend_indices()}
if(step==2)build_base()
if(step==5)run_quartiles(load_cache("analysis"))
if(step==6)run_reclassification(load_cache("analysis"))
if(step==7){scope<-if(length(args)>1)args[2] else "paper";stopifnot(scope%in%c("paper","oecd35"));build_four(scope);gc(FALSE);run_series(load_cache(if(scope=="paper")"four" else "four_oecd35"),scope)}
if(step==8){d<-load_cache("analysis");for(dom in DOMAINS)for(pv in c(TRUE,FALSE)){run_items(d,dom,pv);gc(FALSE)}}
if(step==9){d<-load_cache("analysis");for(dom in DOMAINS)for(pv in c(TRUE,FALSE)){run_correlations(d,dom,pv);gc(FALSE)}}
if(step==10)run_composites(load_cache("analysis"))
if(step==11)run_fixed(load_cache("base_scored"))
if(step==12)run_systems(load_cache("analysis"))
if(step==13){source(file.path(RR,"R/figures.R"));run_figures()}
if(step==15){
  source(file.path(RR,"R/official_2025.R"))
  if(length(args)==1){audit_official_2025();gc(FALSE);build_official_recode_sensitivity();gc(FALSE);build_anchored_2025_sensitivity();gc(FALSE)}
  else stopifnot(args[2]%in%c("summary","report"))
  summarise_technical_2025()
}
cat("R step",step,"completed",format(Sys.time()),"\n")
