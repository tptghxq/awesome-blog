$(function(){
           var conva = new Vue({
        el:'.nav-element',
        data:{newsNum:''},
        ready:function(){
            if('{{__user__.id}}'){
                that =this;
              var t=setTimeout(that.getNewsNum(),3000);  
            }
        },methods:{
        getNewsNum:function(){
            that=this;
            postJSON('/api/getnewsnum',{},function(err,r){
                if(err){
                    showInfo(err);
                    // that.getNewsNum();
                }
                    else if(r.newsNum>0){
                            that.newsNum=r.newsNum;
                            alert(r.newsNum);

                    }
            })
        }
        }
    });
});
         
  