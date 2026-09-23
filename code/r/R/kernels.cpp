#include <Rcpp.h>
using namespace Rcpp;

// Streaming E-step: memory does not grow with persons times quadrature nodes.
// [[Rcpp::export]]
List expectation_cpp(IntegerMatrix X, NumericVector w, NumericVector a,
                     List steps, NumericVector nodes, NumericVector prior) {
  int n=X.nrow(), J=X.ncol(), Q=nodes.size();
  std::vector<NumericMatrix> lp, counts;
  for (int j=0;j<J;j++) {
    NumericVector b=steps[j]; int K=b.size()+1;
    NumericMatrix p(K,Q), r(K,Q);
    for(int q=0;q<Q;q++) {
      double s=0, mx=0, den=0;
      for(int k=1;k<K;k++) {s+=b[k-1]; p(k,q)=a[j]*(k*nodes[q]-s); mx=std::max(mx,p(k,q));}
      for(int k=0;k<K;k++) den+=std::exp(p(k,q)-mx);
      for(int k=0;k<K;k++) p(k,q)-=mx+std::log(den);
    }
    lp.push_back(p); counts.push_back(r);
  }
  double ll=0; std::vector<double> l(Q);
  for(int i=0;i<n;i++) {
    if(i%10000==0) checkUserInterrupt();
    double mx=-INFINITY, den=0;
    for(int q=0;q<Q;q++) {
      l[q]=std::log(prior[q]);
      for(int j=0;j<J;j++) if(X(i,j)!=NA_INTEGER && X(i,j)>=0) l[q]+=lp[j](X(i,j),q);
      mx=std::max(mx,l[q]);
    }
    for(int q=0;q<Q;q++) {l[q]=std::exp(l[q]-mx); den+=l[q];}
    ll+=w[i]*(mx+std::log(den));
    for(int q=0;q<Q;q++) l[q]*=w[i]/den;
    for(int j=0;j<J;j++) if(X(i,j)!=NA_INTEGER && X(i,j)>=0)
      for(int q=0;q<Q;q++) counts[j](X(i,j),q)+=l[q];
  }
  List out(J); for(int j=0;j<J;j++) out[j]=counts[j];
  return List::create(_["counts"]=out,_["loglik"]=ll);
}

// Warm score equation for the canonical GPCM, solved with bounded Newton steps.
// Non-convergence and boundary hits are returned, never silently accepted.
// [[Rcpp::export]]
List wle_cpp(IntegerMatrix X, NumericVector a, List steps, int min_items=3,
             int maxit=100, double tolerance=1e-7) {
  int n=X.nrow(), J=X.ncol();
  NumericVector theta(n,NA_REAL), equation(n,NA_REAL);
  LogicalVector converged(n,false), boundary(n,false);
  std::vector<std::vector<double>> cumul(J);
  for(int j=0;j<J;j++) {
    NumericVector b=steps[j]; cumul[j].push_back(0);
    for(double v:b) cumul[j].push_back(cumul[j].back()+v);
  }
  for(int i=0;i<n;i++) {
    if(i%10000==0) checkUserInterrupt();
    int observed=0; for(int j=0;j<J;j++) observed+=(X(i,j)!=NA_INTEGER && X(i,j)>=0);
    if(observed<min_items) continue;
    double th=0,g=NA_REAL;
    for(int it=0;it<maxit;it++) {
      double score=0, info=0, di=0, d2i=0;
      for(int j=0;j<J;j++) {
        if(X(i,j)==NA_INTEGER || X(i,j)<0) continue;
        int K=cumul[j].size(); std::vector<double> p(K);
        double mx=-INFINITY, den=0, mu=0;
        for(int k=0;k<K;k++) {p[k]=a[j]*(k*th-cumul[j][k]); mx=std::max(mx,p[k]);}
        for(int k=0;k<K;k++) {p[k]=std::exp(p[k]-mx); den+=p[k];}
        for(int k=0;k<K;k++) {p[k]/=den; mu+=k*p[k];}
        double c2=0,c3=0,c4=0;
        for(int k=0;k<K;k++) {double v=k-mu; c2+=p[k]*v*v; c3+=p[k]*v*v*v; c4+=p[k]*v*v*v*v;}
        double aj=a[j]; score+=aj*(X(i,j)-mu); info+=aj*aj*c2;
        di+=aj*aj*aj*c3; d2i+=std::pow(aj,4)*(c4-3*c2*c2);
      }
      if(info<=1e-14) break;
      g=score+di/(2*info);
      if(std::abs(g)<tolerance) {converged[i]=true; break;}
      double h=-info+(d2i*info-di*di)/(2*info*info);
      double step=std::max(-1.0,std::min(1.0,-g/h));
      th=std::max(-12.0,std::min(12.0,th+step));
    }
    theta[i]=th; equation[i]=g; boundary[i]=(std::abs(th)>=12);
  }
  return List::create(_["theta"]=theta,_["converged"]=converged,
                      _["boundary"]=boundary,_["equation"]=equation);
}

// [[Rcpp::export]]
NumericVector group_means_cpp(IntegerMatrix codes, NumericMatrix W, NumericMatrix PV, int K) {
  int n=W.nrow(), R=W.ncol(), M=PV.ncol();
  NumericVector out(K*R*M,0.0); out.attr("dim")=IntegerVector::create(K,R,M);
  for(int r=0;r<R;r++) {
    std::vector<double> den(K,0);
    for(int i=0;i<n;i++) {int k=codes(i,codes.ncol()==1?0:r); if(k>=0 && k<K) den[k]+=W(i,r);}
    for(int m=0;m<M;m++) {
      for(int i=0;i<n;i++) {int k=codes(i,codes.ncol()==1?0:r); if(k>=0 && k<K) out[k+K*r+K*R*m]+=W(i,r)*PV(i,m);}
      for(int k=0;k<K;k++) out[k+K*r+K*R*m]=den[k]>0?out[k+K*r+K*R*m]/den[k]:NA_REAL;
    }
  }
  return out;
}
