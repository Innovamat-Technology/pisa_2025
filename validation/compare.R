# Compare the current, separately generated Python and R outputs.
# Run from the repository root: Rscript validation/compare.R [--individual]
suppressPackageStartupMessages(library(data.table))
setDTthreads(1)
args <- commandArgs(trailingOnly=TRUE)
if(any(!args%in%"--individual")) stop("Usage: Rscript validation/compare.R [--individual]")
root <- normalizePath(Sys.getenv("PISA_REPO","."))
python_dir <- file.path(root,"results/python/tables")
r_dir <- file.path(root,"results/r/tables")
out <- file.path(root,"results/validation")
dir.create(out,recursive=TRUE,showWarnings=FALSE)
write_result <- function(x,name) fwrite(x,file.path(out,paste0(name,".csv")),na="")

comparison_keys <- function(nm) {
  if(grepl("^quartile_check",nm))return(c("cnt","wave","index"))
  if(grepl("^quartiles",nm))return(c("cnt","index"))
  if(grepl("^deciles",nm))return(c("index","decile"))
  if(grepl("^gap_series",nm))return("index")
  if(grepl("^items_validation_groups",nm))return(c("group","wave"))
  if(grepl("^items_validation",nm))return(c("item","wave"))
  if(grepl("^national_items_by_system|^systems_q1_q4|^systems_income",nm))return("cnt")
  if(grepl("^national_items|^irt_parameters",nm))return("item")
  if(grepl("^subscales",nm))return("subscale")
  if(grepl("^correlations",nm))return(c("version","pair"))
  if(grepl("^composite_weights",nm))return("construction")
  if(grepl("^fixed_rules_by_system",nm))return(c("rule","cnt"))
  if(grepl("^fixed_rules",nm))return("rule")
  if(grepl("^fixed_groups",nm))return("group")
  if(grepl("^table4",nm))return(c("wave","group"))
  if(grepl("^transition",nm))return("q_pub")
  if(grepl("^gap_levels|^systems_correlations",nm))return("index")
  "wave"
}
read_output <- function(path,keys) {
  x <- fread(path)
  if(!keys[1]%in%names(x) && names(x)[1]%in%c("V1","","Unnamed: 0")) setnames(x,1,keys[1])
  if(!all(keys%in%names(x))) stop("Missing row keys in ",path)
  for(k in keys) set(x,j=k,value=as.character(x[[k]]))
  if("item"%in%keys) x[,item:=toupper(item)]
  if(anyNA(x[,..keys]) || anyDuplicated(x[,..keys])) stop("Missing or duplicate row keys in ",path)
  x
}
record_file <- function(path) data.table(
  path=substring(path,nchar(root)+2),
  sha256=digest::digest(path,algo="sha256",file=TRUE))

files <- list.files(python_dir,pattern="\\.csv$",full.names=TRUE)
if(!length(files)) stop("No Python tables found in ",python_dir)
coverage <- differences <- manifests <- parameters <- main <- list()
used_r <- character()
for(path in files) {
  nm <- sub("\\.csv$","",basename(path))
  keys <- comparison_keys(nm)
  p <- read_output(path,keys)
  manifests[[length(manifests)+1L]] <- record_file(path)
  # The legacy suffix denotes an older statistical protocol, not current Python.
  for(protocol in c("current_defaults","r_legacy_paper_protocol")) {
    rp <- file.path(r_dir,paste0(nm,if(protocol=="current_defaults")"" else "_paper_protocol",".csv"))
    if(!file.exists(rp)) {
      if(protocol=="current_defaults") coverage[[length(coverage)+1L]] <- data.table(table=nm,r_protocol=protocol,status="missing_r_output")
      next
    }
    used_r <- c(used_r,basename(rp))
    manifests[[length(manifests)+1L]] <- record_file(rp)
    r <- read_output(rp,keys)
    cols_p <- setdiff(names(p)[vapply(p,is.numeric,logical(1))],keys)
    cols_r <- setdiff(names(r)[vapply(r,is.numeric,logical(1))],keys)
    cols <- intersect(cols_p,cols_r)
    missing_cols <- setdiff(cols_p,cols_r)
    missing_r <- nrow(fsetdiff(p[,..keys],r[,..keys]))
    extra_r <- nrow(fsetdiff(r[,..keys],p[,..keys]))
    coverage[[length(coverage)+1L]] <- data.table(
      table=nm,r_protocol=protocol,r_file=basename(rp),
      status=if(length(missing_cols))"missing_numeric_columns" else if(missing_r)"missing_rows" else "covered",
      python_rows=nrow(p),r_rows=nrow(r),matched_rows=nrow(p)-missing_r,
      python_only_rows=missing_r,r_only_rows=extra_r,numeric_columns=length(cols),
      python_only_numeric_columns=paste(missing_cols,collapse=";"),
      r_only_numeric_columns=paste(setdiff(cols_r,cols_p),collapse=";"))
    joined <- merge(p[,c(keys,cols),with=FALSE],r[,c(keys,cols),with=FALSE],by=keys,suffixes=c("_python","_r"))
    labels <- apply(joined[,..keys],1,function(z)paste(paste(keys,z,sep="="),collapse="; "))
    for(col in cols) {
      a <- joined[[paste0(col,"_python")]]; b <- joined[[paste0(col,"_r")]]
      ok <- is.finite(a)&is.finite(b); delta <- b-a
      imax <- if(any(ok))which.max(replace(abs(delta),!ok,-Inf)) else NA_integer_
      differences[[length(differences)+1L]] <- data.table(
        table=nm,r_protocol=protocol,column=col,n_compared=sum(ok),
        missing_mismatch=sum(xor(is.finite(a),is.finite(b))),
        mean_abs_difference=if(any(ok))mean(abs(delta[ok])) else NA_real_,
        max_abs_difference=if(any(ok))abs(delta[imax]) else NA_real_,
        largest_difference_key=labels[imax],python_at_largest=a[imax],r_at_largest=b[imax])
    }
    if(grepl("^irt_parameters",nm) && protocol=="current_defaults") {
      j <- merge(p,r,by=keys,suffixes=c("_python","_r"))
      for(i in seq_len(nrow(j))) {
        a <- jsonlite::fromJSON(j$steps_python[i]); b <- jsonlite::fromJSON(j$steps_r[i])
        if(length(a)!=length(b)) stop("Different IRT category counts for ",nm,": ",j$item[i])
        parameters[[length(parameters)+1L]] <- data.table(model=nm,item=j$item[i],slope_difference=j$a_r[i]-j$a_python[i],max_step_difference=max(abs(b-a)))
      }
    }
    if(grepl("^quartiles_(math|read|scie)$",nm)) {
      domain <- sub("quartiles_","",nm)
      for(language in c("python","r")) {
        x <- if(language=="python")p else r
        x <- x[cnt=="OECD" & index%in%c("escs","escs_h","homepos","homepos_h")]
        main[[length(main)+1L]] <- x[,.(domain=domain,language=language,r_protocol=protocol,cnt,index,
          gap_change=get("Q4-Q1_change"),se=get("Q4-Q1_se"))]
      }
    }
  }
}
coverage <- rbindlist(coverage,fill=TRUE)
differences <- rbindlist(differences,fill=TRUE)
write_result(coverage,"table_coverage")
write_result(differences,"comparison_by_column")
write_result(unique(rbindlist(manifests)),"input_manifest")
if(length(parameters)) write_result(rbindlist(parameters),"irt_parameter_comparison")
if(length(main)) write_result(rbindlist(main),"main_results")
r_only <- setdiff(list.files(r_dir,pattern="\\.csv$"),used_r)
write_result(data.table(file=r_only,status=rep("r_only_extension",length(r_only))),"r_only_outputs")

# Individual comparisons are optional: the table comparison needs no microdata.
individual_ran <- FALSE
if("--individual"%in%args) {
  ppath <- file.path(root,"data/interim/python/indices_h.parquet")
  rpath <- file.path(root,"data/interim/r/analysis.rds")
  if(!file.exists(ppath)||!file.exists(rpath)) stop("Run both analysis workflows before using --individual.")
  keys <- c("wave","cnt","cntstuid")
  indices <- c("hisei_h","pared_h","homepos_h","books_h","escs_h","escs_pca")
  needed <- c(keys,indices)
  r <- as.data.table(readRDS(rpath))[,..needed]
  p <- as.data.table(arrow::read_parquet(ppath,col_select=tidyselect::all_of(needed)))
  for(k in keys) {set(p,j=k,value=as.character(p[[k]]));set(r,j=k,value=as.character(r[[k]]))}
  if(anyNA(p[,..keys])||anyNA(r[,..keys])||anyDuplicated(p[,..keys])||anyDuplicated(r[,..keys])) stop("Missing or duplicate student identifiers.")
  j <- merge(p,r,by=keys,suffixes=c("_python","_r"))
  if(nrow(j)!=nrow(p)||nrow(j)!=nrow(r)) stop("Student samples differ; match the samples before comparing individual scores.")
  rows <- lapply(indices,function(v) {
    a<-j[[paste0(v,"_python")]];b<-j[[paste0(v,"_r")]];ok<-is.finite(a)&is.finite(b)
    data.table(index=v,n=sum(ok),missing_mismatch=sum(xor(is.finite(a),is.finite(b))),
      correlation=if(sum(ok)>1)cor(a[ok],b[ok]) else NA_real_,
      rmse=if(any(ok))sqrt(mean((a[ok]-b[ok])^2)) else NA_real_,
      max_abs_difference=if(any(ok))max(abs(a[ok]-b[ok])) else NA_real_)
  })
  write_result(rbindlist(rows),"person_score_comparison")
  write_result(rbindlist(lapply(c(ppath,rpath),record_file)),"individual_input_manifest")
  individual_ran <- TRUE
}
complete <- all(coverage$status=="covered")
summary <- list(
  compared_utc=format(Sys.time(),"%Y-%m-%dT%H:%M:%SZ",tz="UTC"),
  python_tables=length(files),table_protocol_pairs=nrow(coverage),
  complete_table_coverage=complete,numeric_column_comparisons=nrow(differences),
  missing_value_mismatches=sum(differences$missing_mismatch),
  individual_scores_compared=individual_ran,
  interpretation="Coverage checks structure, not numerical equivalence. Current defaults differ methodologically; the R legacy paper protocol is historical. See the root README.")
jsonlite::write_json(summary,file.path(out,"summary.json"),pretty=TRUE,auto_unbox=TRUE)
writeLines(capture.output(sessionInfo()),file.path(out,"sessionInfo.txt"))
if(!complete) stop("Incomplete table coverage; inspect results/validation/table_coverage.csv")
cat("Compared",length(files),"Python tables across",nrow(coverage),"table/protocol pairs. Results:",out,"\n")
