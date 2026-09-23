# Run from the repository root: Rscript code/r/run_all.R [first_stage] [last_stage].
# Each stage gets a fresh R process to release memory.
args <- commandArgs(trailingOnly=TRUE)
first <- if(length(args)) as.integer(args[1]) else 1L
last <- if(length(args)>1) as.integer(args[2]) else 13L
stopifnot(length(args)<=2, !is.na(first), !is.na(last), first%in%1:13, last%in%1:13, first<=last)
required <- c("data.table","arrow","haven","Rcpp","readxl","ggplot2","jsonlite","digest","tidyselect")
missing <- required[!vapply(required,requireNamespace,logical(1),quietly=TRUE)]
if(length(missing)) stop("Install required R packages: ",paste(missing,collapse=", "))
Sys.setenv(OPENBLAS_NUM_THREADS=1,OMP_NUM_THREADS=1,ARROW_NUM_THREADS=1)
root <- normalizePath(Sys.getenv("PISA_REPO", "."))
out <- file.path(root,"results","r")
logs <- file.path(root,"audit","logs","r")
for(p in c(out,logs)) dir.create(p,recursive=TRUE,showWarnings=FALSE)
stages <- list(c(1),c(2),c(5),c(6),c(7,"paper"),c(7,"oecd35"),c(8),c(9),c(10),c(11),c(12),c(13))
status_path <- file.path(out,"run_status.csv")
status <- if(file.exists(status_path)) {
  previous <- read.csv(status_path,stringsAsFactors=FALSE)
  split(previous,previous$stage)
} else list()
for(stage in stages) {
  if(as.integer(stage[1])<first || as.integer(stage[1])>last) next
  tag <- paste(stage,collapse="_")
  cat("Running R stage",tag,"\n");flush.console()
  logfile <- file.path(logs,paste0("stage_",tag,".log"))
  start <- Sys.time()
  code <- system2(file.path(R.home("bin"),"Rscript"),
                  c(shQuote(file.path(root,"code","r","step.R")),stage),stdout=logfile,stderr=logfile)
  status[[tag]] <- data.frame(stage=tag,exit_code=code,seconds=as.numeric(difftime(Sys.time(),start,units="secs")))
  write.csv(do.call(rbind,status),status_path,row.names=FALSE)
  if(code!=0) stop("Stage ",tag," failed. See ",logfile)
}
writeLines(capture.output(sessionInfo()),file.path(out,"sessionInfo.txt"))
cat("R analysis completed. Results:",out,"\n")
