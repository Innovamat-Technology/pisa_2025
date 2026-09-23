run_figures <- function() {
  suppressPackageStartupMessages(library(ggplot2))
  cols<-c(escs="#2b5c8a",escs_h="#C0370C",homepos="#2b5c8a",homepos_h="#C0370C",hisei_h="#777777",pared_h="#777777",escs_h4="#C0370C",homepos_h4="#C0370C")
  types<-c(escs="solid",escs_h="solid",homepos="dashed",homepos_h="dashed",hisei_h="solid",pared_h="dotted",escs_h4="solid",homepos_h4="dashed")
  labs<-c(escs="ESCS published",escs_h="ESCS harmonized",homepos="HOMEPOS published",homepos_h="HOMEPOS harmonized",hisei_h="HISEI",pared_h="PARED",escs_h4="ESCS harmonized",homepos_h4="HOMEPOS harmonized")
  domain_label<-c(math="mathematics",read="reading",scie="science")
  theme_set(theme_bw(base_size=9)+theme(panel.grid.minor=element_blank(),panel.border=element_blank(),axis.line=element_line(linewidth=.35),legend.position="bottom",legend.title=element_blank()))
  decorate<-function(p) {
    nr<-if(uniqueN(p$data$index)>3)2 else 1
    p<-p+scale_color_manual(values=cols,labels=labs)+guides(color=guide_legend(nrow=nr,byrow=TRUE))
    if("linetype"%in%names(p$mapping))p<-p+scale_linetype_manual(values=types,labels=labs)+guides(linetype=guide_legend(nrow=nr,byrow=TRUE))
    p
  }
  save<-function(p,n,w=5.5,h=3.5){ggsave(file.path(OUT,"figures",paste0(n,".pdf")),p,width=w,height=h,device=cairo_pdf);ggsave(file.path(OUT,"figures",paste0(n,".png")),p,width=w,height=h,dpi=300)}
  profile<-function(q,ind=c("escs","escs_h","homepos","homepos_h","hisei_h","pared_h")) {
    rbindlist(lapply(1:4,function(k)q[index%in%ind,.(cnt,index,quartile=k,change=get(paste0("Q",k,"_change")),se=get(paste0("Q",k,"_se")))]))
  }
  for(dom in DOMAINS) {
    q<-read_table(paste0("quartiles_",dom));d<-profile(q[cnt=="OECD"])
    p<-ggplot(d,aes(quartile,change,color=index,linetype=index,group=index))+geom_hline(yintercept=0,linewidth=.3)+geom_errorbar(aes(ymin=change-1.96*se,ymax=change+1.96*se),width=.06,linewidth=.3)+geom_line()+geom_point(size=1.5)+scale_x_continuous(breaks=1:4,labels=paste0("Q",1:4))+labs(x="Quartile of the index",y=paste("Change in",domain_label[[dom]],"2022–2025 (points)"))
    save(decorate(p)+labs(caption="36 systems; equal country weights; 95% intervals"),paste0("fig_quartile_profiles_",dom))
    s<-read_table(paste0("gap_series_",dom));d<-rbindlist(lapply(c(2015,2018,2022,2025),function(y)s[index%in%c("escs","escs_h4","homepos","homepos_h4"),.(index,wave=y,gap=get(paste0("y",y)),se=get(paste0("se",y)))]))
    p<-ggplot(d,aes(wave,gap,color=index,linetype=index))+geom_errorbar(aes(ymin=gap-1.96*se,ymax=gap+1.96*se),width=.12,linewidth=.3)+geom_line()+geom_point(size=1.5)+scale_x_continuous(breaks=c(2015,2018,2022,2025))+labs(x=NULL,y=paste("Q4 − Q1 gap in",domain_label[[dom]],"(points)"))
    save(decorate(p)+labs(caption=paste(s$n_systems[1],"systems; equal country weights; 95% intervals")),paste0("fig_gap_series_",dom))
    if(file.exists(file.path(OUT,"tables",paste0("gap_series_",dom,"_oecd35.csv")))) {
      s<-read_table(paste0("gap_series_",dom,"_oecd35"));dd<-rbindlist(lapply(c(2015,2018,2022,2025),function(y)s[index%in%c("escs","escs_h4","homepos","homepos_h4"),.(index,wave=y,gap=get(paste0("y",y)),se=get(paste0("se",y)))]))
      save(decorate(p + dd)+labs(caption="OECD-35 country set; equal country weights; 95% intervals"),paste0("fig_gap_series_",dom,"_oecd35"))
    }
    d<-profile(q[!cnt%in%c("OECD","OECD35")],c("escs","escs_h"));order<-q[index=="escs"&!cnt%in%c("OECD","OECD35")][order(get("Q4-Q1_change")),cnt];d[,cnt:=factor(cnt,levels=order)]
    p<-ggplot(d,aes(quartile,change,color=index,group=index))+geom_hline(yintercept=0,linewidth=.2)+geom_line(linewidth=.45)+geom_point(size=.6)+facet_wrap(~cnt,ncol=6)+scale_x_continuous(breaks=1:4,labels=paste0("Q",1:4))+labs(x=NULL,y=paste("Change in",domain_label[[dom]],"2022–2025 (points)"))+theme(strip.background=element_blank(),strip.text=element_text(hjust=0,size=7),axis.text=element_text(size=6))
    save(decorate(p),paste0("fig_systems_",dom),h=6.5)
  }
  q<-read_table("quartiles_math")[cnt=="OECD"&index%in%c("escs","escs_h","homepos_h","pared_h")]
  pairs<-c("Q2-Q1","Q3-Q1","Q3-Q2","Q4-Q1","Q4-Q2","Q4-Q3")
  d<-rbindlist(lapply(pairs,function(nm)q[,.(index,pair=nm,change=get(paste0(nm,"_change")),se=get(paste0(nm,"_se")))]));d[,pair:=factor(pair,levels=pairs)]
  p<-ggplot(d,aes(pair,change,fill=index))+geom_hline(yintercept=0,linewidth=.3)+geom_col(position=position_dodge(.8),width=.75)+geom_errorbar(aes(ymin=change-1.96*se,ymax=change+1.96*se),position=position_dodge(.8),width=.15,linewidth=.3)+scale_fill_manual(values=cols,labels=labs)+labs(x="Difference between quartiles",y="Change in the gap, 2022–2025 (points)")
  save(p+guides(fill=guide_legend(nrow=2,byrow=TRUE)),"fig_pairwise_differences")
  d<-read_table("deciles_math")[index%in%c("escs","escs_h")&decile!="D10-D1"];d[,decile:=as.integer(decile)]
  p<-ggplot(d,aes(decile,change,color=index))+geom_hline(yintercept=0,linewidth=.3)+geom_errorbar(aes(ymin=change-1.96*se,ymax=change+1.96*se),width=.15,linewidth=.3)+geom_line()+geom_point(size=1.5)+scale_x_continuous(breaks=1:10,labels=paste0("D",1:10))+labs(x="Decile of the index",y="Change in mathematics, 2022–2025 (points)")
  save(decorate(p),"fig_decile_profile")
  groupcols<-c("2022 only"="#2b5c8a","common"="#C0370C","2025 only"="#999999")
  for(dom in c("math","scie")) {
    d<-read_table(paste0("items_validation_",dom))[wave==2022|group=="2025 only"];d[,group:=factor(group,levels=names(groupcols))];setorder(d,group,r_score);d[,label:=factor(label,levels=unique(label))]
    p<-ggplot(d,aes(r_score,label,fill=group))+geom_col(width=.7)+geom_vline(xintercept=0,linewidth=.3)+scale_fill_manual(values=groupcols)+labs(x=paste("Mean correlation across plausible values:",domain_label[[dom]]),y=NULL)+theme(axis.text.y=element_text(size=6.5))
    save(p,paste0("fig_item_correlations_",dom),h=7)
  }
  d<-read_table("items_validation_math")[wave==2022|group=="2025 only"]
  p<-ggplot(d,aes(r_hisei,partial_r,color=group))+geom_hline(yintercept=0,linewidth=.3)+geom_vline(xintercept=0,linewidth=.3)+geom_point(size=1.6)+scale_color_manual(values=groupcols)+labs(x="Correlation with parental occupation (HISEI)",y="Partial correlation with mathematics")
  save(p,"fig_item_content")
}
