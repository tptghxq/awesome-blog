// awesome.js

// patch for lower-version IE:

if (! window.console) {
    window.console = {
        log: function() {},
        info: function() {},
        error: function () {},
        warn: function () {},
        debug: function () {}
    };
}

// patch for string.trim():

if (! String.prototype.trim) {
    String.prototype.trim = function() {
        return this.replace(/^\s+|\s+$/g, '');
    };
}
//去重
if (!Array.prototype.unique) {
Array.prototype.unique = function(){
 var res = [];
 var json = {};
 for(var i = 0; i < this.length; i++){
  if(!json[this[i]]){
   res.push(this[i]);
   json[this[i]] = 1;
  }
 }
 return res;
}
}
if (! Number.prototype.toDateTime) {
    var replaces = {
        'yyyy': function(dt) {
            return dt.getFullYear().toString();
        },
        'yy': function(dt) {
            return (dt.getFullYear() % 100).toString();
        },
        'MM': function(dt) {
            var m = dt.getMonth() + 1;
            return m < 10 ? '0' + m : m.toString();
        },
        'M': function(dt) {
            var m = dt.getMonth() + 1;
            return m.toString();
        },
        'dd': function(dt) {
            var d = dt.getDate();
            return d < 10 ? '0' + d : d.toString();
        },
        'd': function(dt) {
            var d = dt.getDate();
            return d.toString();
        },
        'hh': function(dt) {
            var h = dt.getHours();
            return h < 10 ? '0' + h : h.toString();
        },
        'h': function(dt) {
            var h = dt.getHours();
            return h.toString();
        },
        'mm': function(dt) {
            var m = dt.getMinutes();
            return m < 10 ? '0' + m : m.toString();
        },
        'm': function(dt) {
            var m = dt.getMinutes();
            return m.toString();
        },
        'ss': function(dt) {
            var s = dt.getSeconds();
            return s < 10 ? '0' + s : s.toString();
        },
        's': function(dt) {
            var s = dt.getSeconds();
            return s.toString();
        },
        'a': function(dt) {
            var h = dt.getHours();
            return h < 12 ? 'AM' : 'PM';
        }
    };
    var token = /([a-zA-Z]+)/;
    Number.prototype.toDateTime = function(format) {
        var fmt = format || 'yyyy-MM-dd hh:mm:ss'
        var dt = new Date(this * 1000);
        var arr = fmt.split(token);
        for (var i=0; i<arr.length; i++) {
            var s = arr[i];
            if (s && s in replaces) {
                arr[i] = replaces[s](dt);
            }
        }
        return arr.join('');
    };
}

function encodeHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

// parse query string as object:

function parseQueryString() {
    var
        q = location.search,
        r = {},
        i, pos, s, qs;
    if (q && q.charAt(0)==='?') {
        qs = q.substring(1).split('&');
        for (i=0; i<qs.length; i++) {
            s = qs[i];
            pos = s.indexOf('=');
            if (pos <= 0) {
                continue;
            }
            r[s.substring(0, pos)] = decodeURIComponent(s.substring(pos+1)).replace(/\+/g, ' ');
        }
    }
    return r;
}

function gotoPage(i) {
    var r = parseQueryString();
    r.page = i;
    location.assign('?' + $.param(r));
}

function refresh() {
    var
        t = new Date().getTime(),
        url = location.pathname;
    if (location.search) {
        url = url + location.search + '&t=' + t;
    }
    else {
        url = url + '?t=' + t;
    }
    location.assign(url);
}

function toSmartDate(timestamp) {
    if (typeof(timestamp)==='string') {
        timestamp = parseInt(timestamp);
    }
    if (isNaN(timestamp)) {
        return '';
    }

    var
        today = new Date(),
        now = today.getTime(),
        s = '1分钟前',
        t = now - timestamp;
    if (t > 604800000) {
        // 1 week ago:
        var that = new Date(timestamp);
        var
            y = that.getFullYear(),
            m = that.getMonth() + 1,
            d = that.getDate(),
            hh = that.getHours(),
            mm = that.getMinutes();
        s = y===today.getFullYear() ? '' : y + '年';
        s = s + m + '月' + d + '日' + hh + ':' + (mm < 10 ? '0' : '') + mm;
    }
    else if (t >= 86400000) {
        // 1-6 days ago:
        s = Math.floor(t / 86400000) + '天前';
    }
    else if (t >= 3600000) {
        // 1-23 hours ago:
        s = Math.floor(t / 3600000) + '小时前';
    }
    else if (t >= 60000) {
        s = Math.floor(t / 60000) + '分钟前';
    }
    return s;
}



$(function() {
    $('.x-smartdate').each(function() {
        $(this).removeClass('x-smartdate').text(toSmartDate($(this).attr('date')));
    });
});

// JS Template:

function Template(tpl) {
    var
        fn,
        match,
        code = ['var r=[];\nvar _html = function (str) { return str.replace(/&/g, \'&amp;\').replace(/"/g, \'&quot;\').replace(/\'/g, \'&#39;\').replace(/</g, \'&lt;\').replace(/>/g, \'&gt;\'); };'],
        re = /\{\s*([a-zA-Z\.\_0-9()]+)(\s*\|\s*safe)?\s*\}/m,
        addLine = function (text) {
            code.push('r.push(\'' + text.replace(/\'/g, '\\\'').replace(/\n/g, '\\n').replace(/\r/g, '\\r') + '\');');
        };
    while (match = re.exec(tpl)) {
        if (match.index > 0) {
            addLine(tpl.slice(0, match.index));
        }
        if (match[2]) {
            code.push('r.push(String(this.' + match[1] + '));');
        }
        else {
            code.push('r.push(_html(String(this.' + match[1] + ')));');
        }
        tpl = tpl.substring(match.index + match[0].length);
    }
    addLine(tpl);
    code.push('return r.join(\'\');');
    fn = new Function(code.join('\n'));
    this.render = function (model) {
        return fn.apply(model);
    };
}

// extends jQuery.form:

$(function () {
    console.log('Extends $form...');
    $.fn.extend({
        showFormError: function (err) {
            return this.each(function () {
                var
                    $form = $(this),
                    $alert = $form && $form.find('.uk-alert-danger'),
                    fieldName = err && err.data;
                if (! $form.is('form')) {
                    console.error('Cannot call showFormError() on non-form object.');
                    return;
                }
                $form.find('input').removeClass('uk-form-danger');
                $form.find('select').removeClass('uk-form-danger');
                $form.find('textarea').removeClass('uk-form-danger');
                if ($alert.length === 0) {
                    console.warn('Cannot find .uk-alert-danger element.');
                    return;
                }
                if (err) {
                    $alert.text(err.message ? err.message : (err.error ? err.error : err)).removeClass('uk-hidden').show();
                    if (($alert.offset().top - 60) < $(window).scrollTop()) {
                        $('html,body').animate({ scrollTop: $alert.offset().top - 60 });
                    }
                    if (fieldName) {
                        $form.find('[name=' + fieldName + ']').addClass('uk-form-danger');
                    }
                }
                else {
                    $alert.addClass('uk-hidden').hide();
                    $form.find('.uk-form-danger').removeClass('uk-form-danger');
                }
            });
        },
        showFormLoading: function (isLoading) {
            return this.each(function () {
                var
                    $form = $(this),
                    $submit = $form && $form.find('button[type=submit]'),
                    $buttons = $form && $form.find('button');
                    $i = $submit && $submit.find('i'),
                    iconClass = $i && $i.attr('class');
                if (! $form.is('form')) {
                    console.error('Cannot call showFormLoading() on non-form object.');
                    return;
                }
                if (!iconClass || iconClass.indexOf('uk-icon') < 0) {
                    console.warn('Icon <i class="uk-icon-*>" not found.');
                    return;
                }
                if (isLoading) {
                    $buttons.attr('disabled', 'disabled');
                    $i && $i.addClass('uk-icon-spinner').addClass('uk-icon-spin');
                }
                else {
                    $buttons.removeAttr('disabled');
                    $i && $i.removeClass('uk-icon-spinner').removeClass('uk-icon-spin');
                }
            });
        },
        postJSON: function (url, data, callback) {
            if (arguments.length===2) {
                callback = data;
                data = {};
            }
            return this.each(function () {
                var $form = $(this);
                // $form.showFormError();
                // $form.showFormLoading(true);
                _httpJSON('POST', url, data, function (err, r) {
                    if (err) {
                        showInfo(err);
                        // $form.showFormLoading(false);
                    }
                    callback && callback(err, r);
                });
            });
        }
    });
});

// ajax submit form:

function _httpJSON(method, url, data, callback,asy) {
    var opt = {
        type: method,
        dataType: 'json',
        // 修改异步
        async: asy || true    
    };
    if (method==='GET') {
        opt.url = url + '?' + data;
    }
    if (method==='POST') {
        opt.url = url;
        opt.data = JSON.stringify(data || {});
        opt.contentType = 'application/json;charset=utf-8';
    }
    $.ajax(opt).done(function (r) {
        if (r && r.error) {
            return callback(r);
        }
        return callback(null, r);
    }).fail(function (jqXHR, textStatus) {
        return callback({'error': 'http_bad_response', 'data': '' + jqXHR.status, 'message': '网络好像出问题了 (HTTP ' + jqXHR.status + ')'});
    });
}

function getJSON(url, data, callback) {
    if (arguments.length===2) {
        callback = data;
        data = {};
    }
    if (typeof (data)==='object') {
        var arr = [];
        $.each(data, function (k, v) {
            arr.push(k + '=' + encodeURIComponent(v));
        });
        data = arr.join('&');
    }
    _httpJSON('GET', url, data, callback);
}

function postJSON(url, data, callback) {
    if (arguments.length===2) {
        callback = data;
        data = {};
    }
    _httpJSON('POST', url, data, callback);
}

// extends Vue:

if (typeof(Vue)!=='undefined') {
    Vue.filter('datetime', function (value) {
        var d = value;
        if (typeof(value)==='number') {
            d = new Date(value);
        }
        return d.getFullYear() + '-' + (d.getMonth() + 1) + '-' + d.getDate() + ' ' + d.getHours() + ':' + d.getMinutes();
    });

Vue.filter('smarttime', function (timestamp) {
if (typeof(timestamp)==='string') {
        timestamp = parseInt(timestamp);
    }
    if (isNaN(timestamp)) {
        return '';
    }

    var
        today = new Date(),
        now = today.getTime(),
        s = '1分钟前',
        t = now - timestamp;
    if (t > 604800000) {
        // 1 week ago:
        var that = new Date(timestamp);
        var
            y = that.getFullYear(),
            m = that.getMonth() + 1,
            d = that.getDate(),
            hh = that.getHours(),
            mm = that.getMinutes();
        s = y===today.getFullYear() ? '' : y + '年';
        s = s + m + '月' + d + '日' + hh + ':' + (mm < 10 ? '0' : '') + mm;
    }
    else if (t >= 86400000) {
        // 1-6 days ago:
        s = Math.floor(t / 86400000) + '天前';
    }
    else if (t >= 3600000) {
        // 1-23 hours ago:
        s = Math.floor(t / 3600000) + '小时前';
    }
    else if (t >= 60000) {
        s = Math.floor(t / 60000) + '分钟前';
    }
    return s;
    });

    Vue.component('pagination', {
        template: '<ul class="uk-pagination">' +
                '<li v-if="! has_previous" class="uk-disabled"><span><i class="uk-icon-angle-double-left"></i></span></li>' +
                '<li v-if="has_previous"><a v-attr="onclick:\'gotoPage(\' + (page_index-1) + \')\'" href="#0"><i class="uk-icon-angle-double-left"></i></a></li>' +
                '<li class="uk-active"><span v-text="page_index"></span></li>' +
                '<li v-if="! has_next" class="uk-disabled"><span><i class="uk-icon-angle-double-right"></i></span></li>' +
                '<li v-if="has_next"><a v-attr="onclick:\'gotoPage(\' + (page_index+1) + \')\'" href="#0"><i class="uk-icon-angle-double-right"></i></a></li>' +
            '</ul>'
    });
}

function redirect(url) {
    var
        hash_pos = url.indexOf('#'),
        query_pos = url.indexOf('?'),
        hash = '';
    if (hash_pos >=0 ) {
        hash = url.substring(hash_pos);
        url = url.substring(0, hash_pos);
    }
    url = url + (query_pos >= 0 ? '&' : '?') + 't=' + new Date().getTime() + hash;
    console.log('redirect to: ' + url);
    location.assign(url);
}

// init:

function _bindSubmit($form) {
    $form.submit(function (event) {
        event.preventDefault();
        showFormError($form, null);
        var
            fn_error = $form.attr('fn-error'),
            fn_success = $form.attr('fn-success'),
            fn_data = $form.attr('fn-data'),
            data = fn_data ? window[fn_data]($form) : $form.serialize();
        var
            $submit = $form.find('button[type=submit]'),
            $i = $submit.find('i'),
            iconClass = $i.attr('class');
        if (!iconClass || iconClass.indexOf('uk-icon') < 0) {
            $i = undefined;
        }
        $submit.attr('disabled', 'disabled');
        $i && $i.addClass('uk-icon-spinner').addClass('uk-icon-spin');
        postJSON($form.attr('action-url'), data, function (err, result) {
            $i && $i.removeClass('uk-icon-spinner').removeClass('uk-icon-spin');
            if (err) {
                console.log('postJSON failed: ' + JSON.stringify(err));
                $submit.removeAttr('disabled');
                fn_error ? fn_error() : showFormError($form, err);
            }
            else {
                var r = fn_success ? window[fn_success](result) : false;
                if (r===false) {
                    $submit.removeAttr('disabled');
                }
            }
        });
    });
    $form.find('button[type=submit]').removeAttr('disabled');
}

$(function () {
    $('form').each(function () {
        var $form = $(this);
        if ($form.attr('action-url')) {
            _bindSubmit($form);
        }
    });
});

$(function() {
    if (location.pathname === '/' || location.pathname.indexOf('/blog')===0) {
        $('li[data-url=blogs]').addClass('uk-active');
    }
});

function _display_error($obj, err) {
    if ($obj.is(':visible')) {
        $obj.hide();
    }
    var msg = err.message || String(err);
    var L = ['<div class="uk-alert uk-alert-danger">'];
    L.push('<p>Error: ');
    L.push(msg);
    L.push('</p><p>Code: ');
    L.push(err.error || '500');
    L.push('</p></div>');
    $obj.html(L.join('')).slideDown();
}

function error(err) {
    _display_error($('#error'), err);
}

function fatal(err) {
    _display_error($('#loading'), err);
}

function showInfo(info,op) {
    op= op || 0;
    $('.confirm_con').remove();
    $('.alert_bg').remove();
    var s = "<div class='alert_bg'></div><div class='confirm_con'><div class='alert_con'></div></div>"
    $('body').prepend(s).css({overflow: "hidden"});
    $('.alert_bg').fadeIn(300);
    msg=info.message ? info.message : (info.error ? info.error : info);
    if (!op) {
        $('.alert_con').css({"color":"#871724"});
        opText="出错："

};
    if(op) {
            $('.alert_con').css({"color":"#FCD000"});
        opText="提示："
    }
    $('.alert_con').text(opText+msg);
    $('.confirm_con').slideDown(200);
    $('.alert_bg').click(function(){
        $('body').css({overflow: "visible"});
        $('.confirm_con').slideUp(200);
        $('.alert_bg').fadeOut(100);
    });
}

        function getNewsNum(){
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

        function getPageCodes(index,count) {
                pageCodes=[];
                pageCodes.push(index);
                if(count-index<5){
                       var i= count-index;
                }
                else{var i=5}
                if(index<6){
                    var j =index-1;
                }
                else{var j=5;}
                  var pageCode=index;
                    for(;i>0;i--){
                        pageCode++;
                        pageCodes.push(pageCode);                        
                    }
                var pageCode2=index;
                    for(;j>0;j--){
                        pageCode2--;
                        pageCodes.unshift(pageCode2);                     
                    }
                    return pageCodes;
            }

             function deleteItem(item) {
               
                if (confirm('确认要删除 ' + (item.name||item.user_name+' 的这条评论') +'？删除后不可恢复！')) {
                    postJSON('/api/'+item.table+'/' + item.id + '/delete', function (err,r) {
                        if (err) {
                            showInfo(err);
                        }
                        else if(r.id) {
                            if(item.table=='comments'){
                                $('#'+item.id).remove();
                            }
                            else{
                                window.location.replace('/');
                            }
                        }
                    });
                }
            }
// 去除富文本尾部添加标签
function handleHtml(html,str){
    if(html.slice(-str.length)==str){
        html=html.slice(0,-str.length);
                }
    return html;
}

function validateEmail(email) {
    var re = /^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$/;
    return re.test(email.toLowerCase());
}

function parsePath(path) {
names=path.split('/');
lastname=names[names.length-1];
return lastname;
}