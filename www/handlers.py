#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

' url handlers '

import re, time, json, logging, hashlib, base64, asyncio,os,sys
from PIL import Image
import markdown2

from aiohttp import web

from coroweb import get, post
from apis import Page, APIValueError,APIPermissionError,APIResourceNotFoundError,APIError

from models import User, Comment, Blog, Follow,Appreciate,Conversation,next_id
from config import configs


COOKIE_NAME = 'awesession'
_COOKIE_KEY = configs.session.secret

def cropImage(fpath,tpath):
    im = Image.open(fpath)
    w,h =im.size
    if w>h:
      box=((w-h)/2,0,w-(w-h)/2,h)
      newim=im.crop(box)
    elif w<h:
      box=(0,(h-w)/2,w,h-(h-w)/2)    
      newim=im.crop(box)
    else:
      newim=im
    if w>300 and h>300:
      size=(300,300)
      newim.thumbnail(size)
    newim.save(tpath)

def check_admin(request):
    if request.__user__ is None or not request.__user__.admin:
        raise APIPermissionError('no Permission')

def check_passwd(email,passwd):
    if not email:
        raise APIValueError('email', 'Invalid email.')
    if not passwd:
        raise APIValueError('passwd', 'please input password.')
    users = yield from User.findAll('email=?', [email])
    if len(users) == 0:
        raise APIValueError('email', 'Email not exist.')
    user = users[0]
    # check passwd:
    sha1 = hashlib.sha1()
    sha1.update(user.id.encode('utf-8'))
    sha1.update(b':')
    sha1.update(passwd.encode('utf-8'))
    if user.passwd != sha1.hexdigest():
        raise APIValueError('passwd', 'password is fault.')
    return user

def get_page_index(page_str):
    p = 1
    try:
        p = int(page_str)
    except ValueError as e:
        pass
    if p < 1:
        p = 1
    return p

def user2cookie(user, max_age):
    '''
    Generate cookie str by user.
    '''
    # build cookie string by: id-expires-sha1
    expires = str(int(time.time() + max_age))
    s = '%s-%s-%s-%s' % (user.id, user.passwd, expires, _COOKIE_KEY)
    L = [user.id, expires, hashlib.sha1(s.encode('utf-8')).hexdigest()]
    return '-'.join(L)

def text2html(text):
    lines = map(lambda s: '<p>%s</p>' % s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'), filter(lambda s: s.strip() != '', text.split('\n')))
    return ''.join(lines)

@asyncio.coroutine
def cookie2user(cookie_str):
    '''
    Parse cookie and load user if cookie is valid.
    '''
    if not cookie_str:
        return None
    try:
        L = cookie_str.split('-')
        if len(L) != 3:
            return None
        uid, expires, sha1 = L
        if int(expires) < time.time():
            return None
        user = yield from User.find(uid)
        if user is None:
            return None
        s = '%s-%s-%s-%s' % (uid, user.passwd, expires, _COOKIE_KEY)
        if sha1 != hashlib.sha1(s.encode('utf-8')).hexdigest():
            logging.info('invalid sha1')
            return None
        # user.passwd = '******'    这里没必要隐去密码，因为是传给请求处理函数，后面如果更新user的话会导致密码错误
        return user
    except Exception as e:
        logging.exception(e)
        return None

def findAllBlogs(page,order='created_at desc'):
    page_index = get_page_index(page)
    num = yield from Blog.findNumber('count(id)')
    page = Page(num,page_index)
    if num == 0:
        blogs = []
    else:
        blogs = yield from Blog.findAll(orderBy=order, limit=(page.offset, page.limit))
    return {'blogs':blogs,'page':page}


@get('/')
def index(*, page='1'):
    items = yield from findAllBlogs(page,'read_num desc')
    return {
        '__template__': 'blogs.html',
        'page': items['page'],
        'blogs': items['blogs']
    }

@get('/service/dialogue')
def dialogue():
    return{
    '__template__':'dialogue.html'
    }

@post('/api/dialogue/save')
def saveDialugue(request,*,content,friendId):
    user=request.__user__
    if user is None:
        raise APIPermissionError("请登录")

    dialogue=Conversation(from_user_id=user.id,to_user_id=friendId,content=content)
    yield from dialogue.save()
    return {'message':1}

@post('/api/dialogue/get')
def getDialugue(request,*,friendId,page='1'):
    user=request.__user__
    if user is None:
        raise APIPermissionError("请登录")
    where= 'from_user_id in (?,?) and to_user_id in (?,?)'
    ids=[user.id,friendId,user.id,friendId]
    num= yield from Conversation.findNumber('count(id)',where,ids)
    page_index = get_page_index(page)
    page = Page(num,page_index)
    if num == 0:
        dialogues=[]
    else:
        dialogues = yield from Conversation.findAll(where,ids,orderBy='created_at desc', limit=(page.offset, page.limit))
    return {
        'dialogues':dialogues,
        'page':page
    }
@post('/api/getnewsnum')
def getnewsnum(request):
    user=request.__user__
    if user is None:
        raise APIPermissionError("未登录")
    logging.info('sssssssssssssssssssssssssssssssssssssss')
    num= yield from Conversation.findNumber('count(id)','news=1 and to_user_id=?',user.id)
    return {'newsNum':num}

@post('/api/upload')
def savephoto(request):
        user=request.__user__
        if user is None:
            raise APIValueError('请登录后再上传')
        data = yield from request.post()
        nameList=['dialoguePhoto','blogPhoto','headIcon']
        for name in nameList:
            thing=data.get(name,None)
            if thing != None:
                currentName=name
                iofile=thing.file
                break
        if iofile is None:
            raise APIError('上传失败')
        filename= data[currentName].filename
        if currentName == 'headIcon':
            newFileName = user.id+filename[filename.find('.'):]
            user.image='/static/img/'+newFileName
            yield from user.update()
        else:
            newFileName = next_id()+filename[filename.find('.'):]            
        imageUrl='/static/img/'+newFileName
        path=os.path.join(os.path.join(os.path.join(os.path.abspath('.'),'static'),'img'),newFileName)
        with open(path,'wb') as f:
            f.write(iofile.read())
        return imageUrl

# @post('/api/firstphoto')
# def getfirstblogphoto(*,path):
#     tpath=next_id
#     cropImage(path,)

@post('/api/getallblogs')
def getallblogs(*,page='1',order='read_num desc'):
    items = yield from findAllBlogs(page,order)
    return {
        'page': items['page'],
        'blogs': items['blogs']
    }

@post('/api/getlike')
def getlike(request,*,page='1'):
    fromuser = request.__user__
    if request.__user__ is None:
        raise APIPermissionError("请登录")
    appreciates = yield from Appreciate.findAll('user_id=?',fromuser.id)
    if len(appreciates) == 0:
        raise APIResourceNotFoundError('你没有喜欢的博文')
    page_index = get_page_index(page)
    blog_ids = [appreciate.blog_id for appreciate in appreciates]
    where='id in ('+','.join(len(blog_ids)*'?')+')'
    num= yield from Blog.findNumber('count(id)',where,blog_ids)
    page = Page(num,page_index)
    if num == 0:
        blogs = []
    else:
        blogs = yield from Blog.findAll(where,blog_ids,orderBy='created_at desc', limit=(page.offset, page.limit))
    return {
        'blogs': blogs,
        'page': page
        }


@post('/api/focus/users')
def getFocusUsers(request,*,page='1'):
    fromuser = request.__user__
    if request.__user__ is None:
        raise APIPermissionError("请登录")
    follows = yield from Follow.findAll('from_user_id=? or to_user_id=?',[fromuser.id,fromuser.id])
    page_index = get_page_index(page)
    # to_user_ids = [follow.to_user_id for follow in follows]
    user_ids=[]
    for follow in follows:
        if(follow.from_user_id==fromuser.id):
            user_ids.append(follow.to_user_id)
        else:
            user_ids.append(follow.from_user_id)

    where='id in ('+','.join(len(user_ids)*'?')+')'
    num= yield from User.findNumber('count(id)',where,user_ids)
    page = Page(num,page_index)
    if num == 0:
        users = []
    else:
        users = yield from User.findAll(where,user_ids,orderBy='created_at desc', limit=(page.offset, page.limit))
        for user in users:
            user.password="******"
    return {
        'friends': users,
        'page': page
        }

        

@post('/api/focus/blogs')
def getFocusBlogs(request,*,page='1'):
    fromuser = request.__user__
    if request.__user__ is None:
        raise APIPermissionError("请登录")
    follows = yield from Follow.findAll('from_user_id=?',fromuser.id)
    if len(follows) == 0:
        raise APIError('你没有关注的人')
    page_index = get_page_index(page)
    to_user_ids = [follow.to_user_id for follow in follows]
    where='user_id in ('+','.join(len(to_user_ids)*'?')+')'
    num= yield from Blog.findNumber('count(id)',where,to_user_ids)
    if num == 0:
        raise APIError('你关注的人还没有写博客')
    logging.info(num)
    page = Page(num,page_index)
    if num == 0:
        blogs = []
    else:
        blogs = yield from Blog.findAll(where,to_user_ids,orderBy='created_at desc', limit=(page.offset, page.limit))
        return {
        'blogs':blogs,
        'page':page
        }
        


@get('/user/{name}')
def user(name,*,page='1'):
    user = yield from User.find(name,'name')
    if user is None:
        raise APIValueError('404')
    page_index = get_page_index(page)
    num = yield from Blog.findNumber('count(id)','user_name=?',name)
    page = Page(num,page_index)
    if num == 0:
        blogs = []
    else:
        blogs = yield from Blog.findAll('user_name=?',[name],orderBy='created_at desc', limit=(page.offset, page.limit))
    
    return {
        '__template__': 'user.html',
        'page': page,
        'blogs': blogs,
        'user':user
    }


@get('/blog/{id}')
def get_blog(id):
    blog = yield from Blog.find(id)
    blog.read_num=blog.read_num+1
    yield from blog.update()
    comments = yield from Comment.findAll('blog_id=?', [id], orderBy='created_at desc')
    for c in comments:
        c.html_content = c.content
    blog.html_content = blog.content
    return {
        '__template__': 'blog.html',
        'blog': blog,
        'comments': comments
    }
@post('/api/likeblog')
def doLikeBlog(request,*,blog_id,op):
    user = request.__user__
    if user is None:
        raise APIPermissionError('登陆后再点哦')
    appreciate=yield from Appreciate.find(user.id,'user_id',blog_id,'blog_id')
    blog=yield from Blog.find(blog_id)
    if blog is None:
        raise APIResourceNotFoundError('没有这篇博客')
    if appreciate is None:
        if op==1:
            return{'message':0,'reblog':blog}
        appreciate2=Appreciate(user_id=user.id,blog_id=blog_id)
        yield from appreciate2.save()
        blog.like_num=blog.like_num+1
        yield from blog.update()
        return {'message':1,'reblog':blog}
    else:
        if op==1:
            return{'message':1,'reblog':blog}
        yield from appreciate.remove()
        if(blog.like_num>0):
         blog.like_num=blog.like_num-1
         yield from blog.update()
        return {'message':0,'reblog':blog}        

@get('/register')
def register():
    return {
        '__template__': 'register.html'
    }

@get('/signin')
def signin():
    return {
        '__template__': 'signin.html'
    }

@get('/setting')
def change():
    return {
        '__template__': 'setting.html'
    }

@post('/api/follow')
def follow(request,*,ownerid,state):
    fromid=request.__user__.id
    if fromid is None:
        raise APIPermissionError("请登录后关注")
    num = yield from Follow.findNumber('count(id)','from_user_id=\''+fromid+'\' and to_user_id=?',ownerid)
    if state == 'check':
        return dict(message=num)
    if num:
        follow=yield from Follow.find(fromid,'from_user_id',ownerid,'to_user_id')
        yield from follow.remove()
        return dict(message=0)
    else:
        follow=Follow(from_user_id=fromid,to_user_id=ownerid)
        yield from follow.save()
        return dict(message=1)

@post('/api/authenticate')
def authenticate(*, email, passwd):
    user = yield from check_passwd(email,passwd)
    # authenticate ok, set cookie:
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.passwd = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r

@post('/api/setting/password')
def change_password(*, email, passwd,newPassword):
    user = yield from check_passwd(email,passwd)
    sha1 = hashlib.sha1()
    sha1.update(user.id.encode('utf-8'))
    sha1.update(b':')
    sha1.update(newPassword.encode('utf-8'))
    user.passwd=sha1.hexdigest()
    yield from user.update()
    logging.info("%d 的密码修改成功" % user.email)
    return dict(message='sussess')

@get('/signout')
def signout(request):
    referer = request.headers.get('Referer')
    r = web.HTTPFound(referer or '/')
    r.set_cookie(COOKIE_NAME, '-deleted-', max_age=0, httponly=True)
    logging.info('user signed out.')
    return r

@get('/manage')
def manage():
    return 'redirect:/manage/comments'

@get('/manage/{items}')
def manage_comments(items,*, page='1'):
    if items!='blogs' and items!='users' and items!='comments':
        raise APIValueError('404')
    return {
        '__template__': 'manage_items.html',
        'page_index': get_page_index(page)
    }

@get('/manage/blogs/create')
def manage_create_blog(request):
    return {
        '__template__': 'manage_blog_edit.html',
        'id': '',
        'action': '/api/blogs'
    }

@get('/manage/blogs/edit')
def manage_edit_blog(*, id):
    return {
        '__template__': 'manage_blog_edit.html',
        'id': id,
        'action': '/api/blogs/%s' % id
    }

@post('/api/blogs/{id}/comments')
def api_create_comment(id, request, *, content):
    user = request.__user__
    if user is None:
        raise APIPermissionError('Please signin first.')
    if not content or not content.strip():
        raise APIValueError('content')
    blog = yield from Blog.find(id)
    if blog is None:
        raise APIResourceNotFoundError('Blog')
    comment = Comment(blog_id=blog.id, user_id=user.id, user_name=user.name, user_image=user.image, content=content.strip())
    yield from comment.save()
    return comment

@post('/api/comments/{id}/delete')
def api_delete_comments(id, request):
    c = yield from Comment.find(id)
    if c is None:
        raise APIResourceNotFoundError('Comment')
    if request.__user__.admin or c.user_id==request.__user__.id:
        yield from c.remove()
        return dict(id=id)

@post('/api/users/{id}/delete')
def api_delete_users(id, request):
    c = yield from User.find(id)
    if c is None:
        raise APIResourceNotFoundError('Comment')
    if request.__user__.admin:
        yield from c.remove()
        return dict(id=id)


@get('/api/{tablename}')
def api_items(tablename,*, page='1'):
    selects={'users':User,'comments':Comment,'blogs':Blog}
    Item=selects.get(tablename,None)
    if Item is None:
        raise APIValueError('404')
    page_index = get_page_index(page)
    num = yield from Item.findNumber('count(id)')
    p = Page(num, page_index)
    if num == 0:
        return dict(page=p, items=())
    items = yield from Item.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
    if Item !=Comment:
        for item in items:
            if Item==User:
                item.password="******"
            if Item==Blog:
                if len(item.name)>25:
                    item.name=item.name[:25]+' ···'
    return dict(page=p, items=items)

_RE_EMAIL = re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
_RE_SHA1 = re.compile(r'^[0-9a-f]{40}$')

@post('/api/register')
def api_register_user(*, email, name, passwd):
    if not name or not name.strip():
        raise APIValueError('name')
    if not email or not _RE_EMAIL.match(email):
        raise APIValueError('email')
    if not passwd or not _RE_SHA1.match(passwd):
        raise APIValueError('passwd')
    users = yield from User.findAll('email=?', [email])
    users2 = yield from User.findAll('name=?', [name])
    if len(users) > 0:
        raise APIError('register:failed', 'email', 'Email is already in use.')
    if len(users2) > 0:
        raise APIError('register:failed', 'name', 'name is already in use.')
    uid = next_id()
    sha1_passwd = '%s:%s' % (uid, passwd)
    # 'http://www.gravatar.com/avatar/%s?d=mm&s=120' % hashlib.md5(email.encode('utf-8')).hexdigest()
    user = User(id=uid, name=name.strip(), email=email, passwd=hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest(), image='/static/img/user.png')
    yield from user.save()
    # make session cookie:
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.passwd = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r

@get('/api/blogs/{id}')
def api_get_blog(*, id):
    blog = yield from Blog.find(id)
    return blog

@post('/api/blogs')
def api_create_blog(request, *, name, summary, content,image):
    if request.__user__ is None:
        raise APIPermissionError('请登录后再写博文')
    if not name or not name.strip():
        raise APIValueError('name', 'name cannot be empty.')
    if not content or not content.strip():
        raise APIValueError('content', 'content cannot be empty.')

    argsList={'user_id':request.__user__.id,'user_name':request.__user__.name,'user_image':request.__user__.image,'name':name.strip(),'content':content.strip()}
    if image:
        argsList['image']=image
    if summary:
        argsList['summary']=summary
    blog = Blog(**argsList)
    yield from blog.save()
    return blog

@post('/api/blogs/{id}')
def api_update_blog(id, request, *, name, summary, content,image):
    blog = yield from Blog.find(id)
    if request.__user__.admin or request.__user__.id == blog.user_id :
        if not name or not name.strip():
            raise APIValueError('name', 'name cannot be empty.')
        if not content or not content.strip():
            raise APIValueError('content', 'content cannot be empty.')
        blog.name = name.strip()
        blog.summary = summary.strip()
        blog.content = content.strip()
        blog.update_at = time.time()
        if image:
            blog.image=image
        if summary:
            blog.summary=summary
        yield from blog.update()
        return blog
    else:
        raise APIPermissionError('you have not permission')

@post('/api/blogs/{id}/delete')
def api_delete_blog(request, *, id):
    blog = yield from Blog.find(id)
    if blog is None:
        raise APIResourceNotFoundError('blog')
    if not request.__user__.admin and blog.user_id!=request.__user__.id:
        raise APIPermissionError('no Permission')
    yield from blog.remove()
    comments = yield from Comment.findAll('blog_id=?', [id], orderBy='created_at desc')
    if len(comments) != 0:
        for comment in comments:
            yield from comment.remove()
    return dict(id=id)
