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

from models import User, Comment, Blog,Agree, Follow,Appreciate,Conversation,next_id
from config import configs


COOKIE_NAME = 'awesession'
_COOKIE_KEY = configs.session.secret


def cropImage(fpath,tpath):
    im = Image.open(fpath)
    if im:
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

@post('/api/firstphoto')
def getfirstblogphoto(*,url):
    oldname=url.split('/')[-1]
    newname=next_id()+url[url.find('.'):]
    fpath = os.path.join(os.path.join(os.path.join(os.path.abspath('.'),'static'),'img'),oldname)
    tpath = os.path.join(os.path.join(os.path.join(os.path.abspath('.'),'static'),'img'),newname)
    cropImage(fpath,tpath)
    newUrl='/static/img/'+newname
    return {'url':newUrl}

@post('/upload/headphoto')
def saveheadphoto(request,*,headValues):
    user=request.__user__
    if user is None:
        raise APIPermissionError('请登录后上传头像')
    oldname=headValues['url'].split('/')[-1]
    newname=next_id()+headValues['url'][headValues['url'].find('.'):]
    logging.info(oldname,newname)
    fpath = os.path.join(os.path.join(os.path.join(os.path.abspath('.'),'static'),'img'),oldname)
    tpath = os.path.join(os.path.join(os.path.join(os.path.abspath('.'),'static'),'img'),newname)
    im = Image.open(fpath)
    size=(headValues['w'],headValues['h'])
    im.thumbnail(size)
    box = (headValues['x'],headValues['y'],headValues['x2'],headValues['y2'])
    newim = im.crop(box)
    newim.thumbnail((100,100))
    newim.save(tpath)
    user.image='/static/img/'+newname
    yield from user.update()
    return{'message':1}

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
def getRelationsUsers(request,*,page='1'):
    fromuser = request.__user__
    if request.__user__ is None:
        raise APIPermissionError("请登录")
    follows = yield from Follow.findAll('from_user_id=? or to_user_id=?',[fromuser.id,fromuser.id])
    if len(follows) ==0:
        raise APIError('没有关注的人')
    page_index = get_page_index(page)
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
def getuser(name,request,*,page='1'):
    user = yield from User.find(name,'name')
    selfUser = request.__user__
    if user is None:
        raise APIValueError('404')
    user.passwd='******'
    if selfUser:
        num = yield from Follow.findNumber('count(id)','from_user_id=\''+selfUser.id+'\' and to_user_id=?',user.id) 
        user.followstate=num
    else:
        user.followstate=0
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

@get('/user/{name}/follower')
def getFollower(name,request,*,page='1'):
    user = yield from User.find(name,'name')
    if user is None:
        raise APIValueError('404')
    selfUser=request.__user__
    if selfUser:
        num = yield from Follow.findNumber('count(id)','from_user_id=\''+selfUser.id+'\' and to_user_id=?',user.id) 
        user.followstate=num
    else:
        user.followstate=0
    user.passwd='******'  
    follows = yield from Follow.findAll('to_user_id=?',[user.id],orderBy='created_at desc')
    if len(follows) == 0:
        page=Page(0,1)
        return {
        '__template__': 'user.html',
        'page': page,
        'followers': [],
        'user': user
        }
    from_user_ids = [follow.from_user_id for follow in follows]
    where='id in ('+','.join(len(from_user_ids)*'?')+')'
    num = yield from User.findNumber('count(id)',where,from_user_ids)
    page_index = get_page_index(page)
    page = Page(num,page_index)
    if num == 0:
        followers = []
    else:
        followers = yield from User.findAll(where,from_user_ids,orderBy='created_at desc', limit=(page.offset, page.limit))
        for follower in followers:
            follower.password="******"
            if selfUser:
                num = yield from Follow.findNumber('count(id)','from_user_id=\''+selfUser.id+'\' and to_user_id=?',follower.id) 
                follower.followstate=num
            else:
                follower.followstate=0
    return {
        '__template__': 'user.html',
        'page': page,
        'followers': followers,
        'user': user
    }

@get('/user/{name}/following')
def getFollowing(name,request,*,page='1'):
    user = yield from User.find(name,'name')
    if user is None:
        raise APIValueError('404')
    user.passwd='******'
    selfUser = request.__user__
    if selfUser:
        num = yield from Follow.findNumber('count(id)','from_user_id=\''+selfUser.id+'\' and to_user_id=?',user.id) 
        user.followstate=num
    follows = yield from Follow.findAll('from_user_id=?',[user.id],orderBy='created_at desc')
    if len(follows) == 0:
        page=Page(0,1)
        return {
        '__template__': 'user.html',
        'page': page,
        'followers': [],
        'user': user
        }
    to_user_ids = [follow.to_user_id for follow in follows]
    where='id in ('+','.join(len(to_user_ids)*'?')+')'
    num= yield from User.findNumber('count(id)',where,to_user_ids)
    page_index = get_page_index(page)
    page = Page(num,page_index)
    if num == 0:
        followings = []
    else:
        followings = yield from User.findAll(where,to_user_ids,orderBy='created_at desc', limit=(page.offset, page.limit))
        for following in followings:
            following.password="******"
            if selfUser:
                num = yield from Follow.findNumber('count(id)','from_user_id=\''+selfUser.id+'\' and to_user_id=?',following.id) 
                following.followstate=num
            else:
                following.followstate=0
    return {
        '__template__': 'user.html',
        'page': page,
        'followings': followings,
        'user':user
    }



@get('/blog/{id}')
def get_blog(id,request,*,page='1'):
    selfUser=request.__user__
    blog = yield from Blog.find(id)
    blog.read_num=blog.read_num+1
    yield from blog.update()
    if blog.image is None:
        blog.image=""
    if blog.summary is None:
        blog.summary=""
    page_index = get_page_index(page)
    num= yield from Comment.findNumber('count(id)','blog_id=?',id)
    page = Page(num,page_index)
    if selfUser:
        appreciate=yield from Appreciate.find(selfUser.id,'user_id',blog.id,'blog_id')
        if appreciate is None:
            blog.likestate=0
        else:
            blog.likestate=1  
    else:
        blog.likestate=0 
    comments = yield from Comment.findAll('blog_id=?', [id], orderBy='agree_num desc',limit=(page.offset, page.limit))
    if len(comments) == 0:
        return{
        '__template__': 'blog.html',
        'blog': blog,
        'comments': []
        }
    for comment in comments:
        if selfUser:
            agree=yield from Agree.find(selfUser.id,'user_id',comment.id,'comment_id')
            if agree is None:
                comment.agreestate=0
            else:
                if agree.state:
                    comment.agreestate=1
                else:
                    comment.agreestate=-1
        else:
            comment.agreestate=0          
    return {
        '__template__': 'blog.html',
        'blog': blog,
        'comments': comments
    }


@post('/api/likeblog')
def doLikeBlog(request,*,blog_id):
    blog=yield from Blog.find(blog_id)
    user = request.__user__
    if blog is None:
        raise APIResourceNotFoundError('没有这篇博客')
    if user is None:
        raise APIPermissionError('请登陆后再喜欢哦')
    appreciate=yield from Appreciate.find(user.id,'user_id',blog_id,'blog_id')   
    if appreciate is None:
        appreciate2=Appreciate(user_id=user.id,blog_id=blog_id)
        yield from appreciate2.save()
        blog.like_num=blog.like_num+1
        yield from blog.update()
        return {'likestate':1,'like_num':blog.like_num}
    else:
        yield from appreciate.remove()
        if(blog.like_num>0):
         blog.like_num=blog.like_num-1
         yield from blog.update()
         logging.info('喜欢数是谁谁谁水水水水水水水水谁谁谁：%s' % blog.like_num)
        return {'likestate':0,'like_num':blog.like_num}        

# state:当前状态 0代表踩，1代表赞；op:动作 1代表点赞按钮 -1代表点踩按钮
@post('/api/agree')
def doagree(request,*,comment_id,op):
    user = request.__user__
    if user is None:
        raise APIPermissionError('请登录')
    comment=yield from Comment.find(comment_id)
    if comment is None:
        raise APIResourceNotFoundError('没有这条评论')    
    agree=yield from Agree.find(user.id,'user_id',comment_id,'comment_id')    
    if comment.user_id == user.id:
        raise APIPermissionError('不能赞或踩自己')
    if agree is None:
        # 点赞
        if op==1:     
            agree2=Agree(user_id=user.id,comment_id=comment_id,state=1)
            yield from agree2.save()
            comment.agree_num=comment.agree_num+1
            yield from comment.update()
            agreestate=1
        if op==-1:
            agree2=Agree(user_id=user.id,comment_id=comment_id,state=0)
            yield from agree2.save()
            comment.disagree_num=comment.disagree_num+1
            yield from comment.update()
            agreestate=-1
    else:
        if op==1:
            if agree.state==1:
                yield from agree.remove()
                comment.agree_num=comment.agree_num-1
                yield from comment.update()
                agreestate=0
            else:
                agree.state=1
                yield from agree.update()
                comment.agree_num=comment.agree_num+1
                comment.disagree_num=comment.disagree_num-1
                yield from comment.update()
                agreestate=1
        if op==-1:
            if agree.state==0:
                yield from agree.remove()
                comment.disagree_num=comment.disagree_num-1
                yield from comment.update()
                agreestate=0
            else:
                agree.state=0
                yield from agree.update()
                comment.disagree_num=comment.disagree_num+1
                comment.agree_num=comment.agree_num-1
                yield from comment.update()
                agreestate=-1
    return{'agreestate':agreestate,'agreenum':comment.agree_num,'disagreenum':comment.disagree_num}

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
def follow(request,*,ownerId,ownerName):
    user=request.__user__
    fromid=user.id
    if fromid is None:
        raise APIPermissionError("请登录后关注")
    num = yield from Follow.findNumber('count(id)','from_user_id=\''+fromid+'\' and to_user_id=?',ownerId)
    if num:
        follow=yield from Follow.find(fromid,'from_user_id',ownerId,'to_user_id')
        yield from follow.remove()
        if user.following_num>0:
            user.following_num=user.following_num-1
            yield from user.update()
        touser=yield from User.find(ownerId)
        if touser.follower_num>0:
            touser=yield from User.find(ownerId)
            touser.follower_num=touser.follower_num-1
            yield from touser.update()
        return dict(followstate=0)
    else:
        follow=Follow(from_user_id=fromid,to_user_id=ownerId,from_user_name=user.name,to_user_name=ownerName)
        yield from follow.save()
        user.following_num=user.following_num+1
        yield from user.update()
        touser=yield from User.find(ownerId)
        touser.follower_num=touser.follower_num+1
        yield from touser.update()
        return dict(followstate=1)

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
def manage_create_blog():
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
        raise APIResourceNotFoundError('发表评论失败，博客可能被删除')
    blog.review_num=blog.review_num+1;
    yield from blog.update()
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
    blog = yield from Blog.find(c.blog_id)
    if blog is None:
        raise APIResourceNotFoundError('这篇博客不存在，可能已被删除')
    blog.review_num = blog.review_num-1
    yield from blog.update()
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
def api_create_blog(request, *, name,summary,content,image):
    if request.__user__ is None:
        raise APIPermissionError('请登录后再写博文')
    if not name or not name.strip():
        raise APIValueError('name', 'name cannot be empty.')
    if not content or not content.strip():
        raise APIValueError('content', 'content cannot be empty.')

    argsList={'user_id':request.__user__.id,'user_name':request.__user__.name,'user_image':request.__user__.image,'name':name.strip(),'content':content.strip()}
    if summary:
        argsList['summary']=summary
    if image:
        argsList['image']=image
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
