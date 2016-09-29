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

from models import User, Comment, Blog,Agree, Follow,Appreciate,Conversation,next_id,Tag_relation,Tag,Atwho
from config import configs


COOKIE_NAME = 'awesession'
_COOKIE_KEY = configs.session.secret

# 可以得到分页的全部或部分对象
def getobjectbypage(Item,**kw):
    if Item is None:
        raise APIValueError('404')
    orderBy = kw.get('orderBy', None)
    if orderBy is None:
        orderBy = 'created_at desc'
    page = kw.get('page', None)
    if page is None:
        page = '1'
    where = kw.get('where', None)
    if where is None:
        where = None
    args = kw.get('args', None)
    if args is None:
        args = None
    page_index = get_page_index(page)
    num = yield from Item.findNumber('count(id)',where,args)
    p = Page(num, page_index)
    if num == 0:
        return dict(page=p, items=())
    items = yield from Item.findAll(where,args,orderBy=orderBy, limit=(p.offset, p.limit))
    if Item==User:
        for item in items:
                item.passwd="******"
    return dict(page=p, items=items)

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

def formatLimit(formatName):
    formatNames=['jpg','png','gif','jpeg']
    for name in formatNames:
        if name == formatName:
            return True
    return False

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

@get('/')
def index(*, page='1'):
    obj = yield from getobjectbypage(Blog,page=page,orderBy='read_num desc')
    return {
        '__template__':'blogs.html',
        'page': obj['page'],
        'blogs': obj['items']
    }

@get('/service/dialogue')
def getdialogue():
    return{
    '__template__':'dialogue.html'
    }

@get('/service/mentions')
def getmention(request,*,page='1'):
    selfUser= request.__user__
    if selfUser is None:
        raise APIPermissionError('请登录后获取提醒')
    obj = yield from getobjectbypage(Atwho,where='to_user_id=?',args=[selfUser.id])
    newsnum =  yield from Atwho.findNumber('count(id)','to_user_id=? and news=?',[selfUser.id,1])
    return{
    '__template__':'mentions.html',
    'mentions':obj['items'],
    'newsnum':newsnum,
    'page':obj['page']
    }

@post('/api/dialogue/save')
def saveDialugue(request,*,content,friendId):
    user=request.__user__
    if user is None:
        raise APIPermissionError("请登录")
    if not content:
        return{'message':0}
    dialogue=Conversation(from_user_id=user.id,to_user_id=friendId,content=content)
    yield from dialogue.save()
    return {'message':1}

@post('/api/dialogue/get')
def getDialugue(request,*,friendId,op,page='1'):
    user=request.__user__
    if user is None:
        raise APIPermissionError("请登录")
    if op == 1:
        where= 'from_user_id in (?,?) and to_user_id in (?,?)'
        ids=[user.id,friendId,user.id,friendId]
    if op == 2:
        where= 'news=1 and from_user_id in (?,?) and to_user_id in (?,?)'
        ids=[user.id,friendId,user.id,friendId]
    if op == 3:
        where= 'news=1 and from_user_id = ? and to_user_id = ?'
        ids=[friendId,user.id]
    
    obj = yield from getobjectbypage(Conversation,where=where,args=ids,page=page)
    dialogues=obj['items']
    for dialogue in dialogues:
        #如果是收信人请求就把信息变为已阅读状态
        if dialogue.to_user_id == user.id:
            dialogue.news=0
            yield from dialogue.update()
    return {
        'dialogues':dialogues,
        'page':obj['page']
    }

@post('/api/getnewsnum')
def getnewsnum(request):
    user=request.__user__
    if user is None:
        raise APIPermissionError("未登录")
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
        formatName = filename[filename.find('.')+1:]
        if not formatLimit(formatName):
            raise APIValueError('请选择jpg,jpeg,png,gif格式的图片')   
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

@post('/api/gethotblogs')
def gethotblogs(*,page='1'):
    obj = yield from getobjectbypage(Blog,where='read_num>?',args=[30],page=page,orderBy='read_num desc')
    return {
        'page': obj['page'],
        'blogs': obj['items']
    }

@post('/api/getnewblogs')
def getallblogs(*,page='1'):
    obj = yield from getobjectbypage(Blog,page=page)
    return {
        'page': obj['page'],
        'blogs': obj['items']
    }

@post('/api/getlikeblogs')
def getlikeblogs(request,*,page='1'):
    fromuser = request.__user__
    if request.__user__ is None:
        raise APIPermissionError("请登录")
    appreciates = yield from Appreciate.findAll('user_id=?',fromuser.id)
    if len(appreciates) == 0:
        return {
          'blogs':[],
        'page': Page(0,1)  
        }
    blog_ids = [appreciate.blog_id for appreciate in appreciates]
    where='id in ('+','.join(len(blog_ids)*'?')+')'
    obj = yield from getobjectbypage(Blog,where=where,args=blog_ids,page=page)
    return {
        'blogs': obj['items'],
        'page': obj['page']
        }

@post('/api/getfocusblogs')
def getFocusBlogs(request,*,page='1'):
    fromuser = request.__user__
    if request.__user__ is None:
        raise APIPermissionError("请登录")
    follows = yield from Follow.findAll('from_user_id=?',fromuser.id)
    if len(follows) == 0:
        raise APIError('你没有关注的人')
    to_user_ids = [follow.to_user_id for follow in follows]
    where='user_id in ('+','.join(len(to_user_ids)*'?')+')'
    obj = yield from getobjectbypage(Blog,where=where,args=to_user_ids,page=page)
    return {
    'blogs':obj['items'],
    'page':obj['page']
    }

@post('/api/focus/users')
def getRelationsUsers(request,*,page='1'):
    selfUser = request.__user__
    if selfUser is None:
        raise APIPermissionError("请登录")
    follows = yield from Follow.findAll('from_user_id=? or to_user_id=?',[selfUser.id,selfUser.id])
    if len(follows) ==0:
        return {
        'friends':[],
        'page':Page(0,1)
        }
    else:       
        friends=[]
        friendIds=[]
        for follow in follows:
            if(follow.from_user_id==selfUser.id):
                friendIds.append(follow.to_user_id)
            else:
                friendIds.append(follow.from_user_id)
        where='id in ('+','.join(len(friendIds)*'?')+')'
        obj =yield from getobjectbypage(User,where=where,args=friendIds,page=page)
        friends=obj['items']
        for friend in friends:
            newsnum = yield from Conversation.findNumber('count(id)','news=1 and to_user_id=? and from_user_id=?',[selfUser.id,friend.id])
            friend.newsnum=newsnum
        return {
        'friends': friends ,
        'page': obj['page']
        }

@get('/api/{name}/tag/{tagname}/delete')
def deletetag(name,tagname,request):
    user = yield from User.find(name,'name')
    if user is None:
        raise APIValueError('404')
    selfUser = request.__user__
    if selfUser is None or selfUser.id !=user.id:
        raise APIPermissionError('你没有权限删除该标签')
    tag=yield from Tag.find(tagname,'name')
    if tag is None:
        APIResourceNotFoundError('该标签不存在')
    tag_relations =yield from Tag_relation.findAll('user_id=? and tag_name=?',[selfUser.id,tagname])
    if len(tag_relations):
        for tag_relation in tag_relations:
            yield from tag_relation.remove()
    yield from tag.remove()
    return {'message':1}

@get('/user/{name}/tag/{tagname}')
def gettagblogs(name,tagname,request,*,page='1'):
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
    tag_relations = yield from Tag_relation.findAll('user_id=? and tag_name=?',[user.id,tagname])
    if len(tag_relations) == 0:
        blogs=[]
    blog_ids = [tag_relation.blog_id for tag_relation in tag_relations]
    where='id in ('+','.join(len(blog_ids)*'?')+')'
    obj =yield from getobjectbypage(Blog,where=where,args=blog_ids,page=page)
    tags = yield from Tag.findAll('user_id=?',user.id)
    return {
        '__template__':'user.html',
        'page': obj['page'],
        'blogs':obj['items'],
        'user':user,
        'tags':tags
    }

@get('/user/{name}')
def getuser(name,request,*,page='1'):
    user = yield from User.find(name,'name')
    selfUser = request.__user__
    if user is None:
        raise APIValueError('404')
    user.passwd='******'
    if selfUser:
        num = yield from Follow.findNumber('count(id)','from_user_id=? and to_user_id=?',[selfUser.id,user.id]) 
        user.followstate=num
    else:
        user.followstate=0
    obj = yield from getobjectbypage(Blog,where='user_name=?',args=[name],page=page)
    tags = yield from Tag.findAll('user_id=?',[user.id],orderBy='num desc')
    return {
        '__template__': 'user.html',
        'page': obj['page'],
        'blogs': obj['items'],
        'user':user,
        'tags':tags
    }

@get('/user/{name}/follower')
def getFollower(name,request,*,page='1'):
    user = yield from User.find(name,'name')
    if user is None:
        raise APIValueError('404')
    selfUser=request.__user__
    if selfUser:
        num = yield from Follow.findNumber('count(id)','from_user_id=? and to_user_id=?',[selfUser.id,user.id]) 
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
    obj=yield from getobjectbypage(User,where=where,args=from_user_ids,page=page)
    followers = obj['items']
    for follower in followers:
            if selfUser:
                num = yield from Follow.findNumber('count(id)','from_user_id=\''+selfUser.id+'\' and to_user_id=?',follower.id) 
                follower.followstate=num
            else:
                follower.followstate=0
    return {
        '__template__': 'user.html',
        'page': obj['page'],
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
        num = yield from Follow.findNumber('count(id)','from_user_id=? and to_user_id=?',[selfUser.id,user.id]) 
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
    obj =yield from getobjectbypage(User,where=where,args=to_user_ids,page=page)
    followings =obj['items']
    for following in followings:
            if selfUser:
                num = yield from Follow.findNumber('count(id)','from_user_id=? and to_user_id=?',[selfUser.id,following.id]) 
                following.followstate=num
            else:
                following.followstate=0
    return {
        '__template__': 'user.html',
        'page': obj['page'],
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
    if selfUser:
        appreciate=yield from Appreciate.find(selfUser.id,'user_id',blog.id,'blog_id')
        if appreciate is None:
            blog.likestate=0
        else:
            blog.likestate=1  
    else:
        blog.likestate=0 
    tag_relations = yield from Tag_relation.findAll('blog_id=?',blog.id)
    if len(tag_relations)==0:
        tagnames=[]
    else:
        tagnames = [tag_relation.tag_name for tag_relation in tag_relations]
    obj = yield from getobjectbypage(Comment,where='blog_id=?',args=[id],page=page,orderBy='agree_num desc')
    comments =obj['items']
    if len(comments) == 0:
       comments=[]
    else:
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
        'comments': comments,
        'tagnames':tagnames,
        'page':obj['page']
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
        appreciate2=Appreciate(user_id=user.id,user_name=user.name,blog_id=blog_id,blog_name=blog.name)
        yield from appreciate2.save()
        blog.like_num=blog.like_num+1
        yield from blog.update()
        return {'likestate':1,'like_num':blog.like_num}
    else:
        yield from appreciate.remove()
        if(blog.like_num>0):
         blog.like_num=blog.like_num-1
         yield from blog.update()
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

@post('/api/setting/base')
def setbase(request,*,age,gender,address):
    user = request.__user__
    if user is None:
        raise APIPermissionError('请登录')
    user.age = age
    user.gender=gender
    user.address=address
    yield from user.update()
    return {'message':1}

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
def api_create_comment(id, request, *, content,atNameAndIds):
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
    comment = Comment(blog_id=blog.id,blog_name=blog.name,user_id=user.id, user_name=user.name, user_image=user.image, content=content.strip())
    yield from comment.save()
    if len(atNameAndIds) != 0:
        for atNameAndId in atNameAndIds:
            toUser = yield from User.find(atNameAndId['name'],'name')
            if toUser:
                atwho = Atwho(id=atNameAndId['uuid'],from_user_id=user.id,from_user_name=user.name,to_user_id=toUser.id,to_user_name=toUser.name,blog_id=blog.id,blog_name=blog.name)
                yield from atwho.save()
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
def api_items(tablename,request,*,page='1'):
    selfUser=request.__user__
    if selfUser is None:
        raise APIPermissionError('请登录')
    selects={'users':User,'comments':Comment,'blogs':Blog,'atwho':Atwho,'conversation':Conversation}
    Item=selects.get(tablename,None)
    obj = yield from getobjectbypage(Item,page=page)
    return dict(page=obj['page'], items=obj['items'])

@get('/mentions/getatwhos')
def getatwho(request,*,op,page='1'):
    selfUser=request.__user__
    if selfUser is None:
        raise APIPermissionError('请登录')
    where='to_user_id=? and news=?'
    args=[selfUser.id,1]
    newsnum =  yield from Atwho.findNumber('count(id)',where,args)
    if op =='1':
        where='to_user_id=?'
        args=[selfUser.id]
    obj=yield from getobjectbypage(Atwho,page=page,where=where,args=args)
    return {
    'page':obj['page'],
    'mentions':obj['items'],
    'newsnum':newsnum
    }

@get('/mentions/getfollow')
def getfollowmentions(request,*,op,page='1'):
    selfUser=request.__user__
    if selfUser is None:
        raise APIPermissionError('请登录')
    where='to_user_id=? and news=?'
    args=[selfUser.id,1]
    newsnum =  yield from Follow.findNumber('count(id)',where,args)
    if op =='1':
        where='to_user_id=?'
        args=[selfUser.id]
    obj=yield from getobjectbypage(Follow,page=page,where=where,args=args)
    return {
    'page':obj['page'],
    'mentions':obj['items'],
    'newsnum':newsnum
    }

@get('/mentions/getcomments')
def getcomments(request,*,op,page='1'):
    selfUser=request.__user__
    if selfUser is None:
        raise APIPermissionError('请登录')
    # args要用list装起来
    blogs=yield from Blog.findAll('user_id=?',[selfUser.id])
    blog_ids= [blog.id for blog in blogs]
    args=blog_ids
    where='news=1 and blog_id in ('+','.join(len(blog_ids)*'?')+')'
    newsnum= yield from Comment.findNumber('count(id)',where,args)
    if op =='1':
        where='blog_id in ('+','.join(len(blog_ids)*'?')+')'
        obj=yield from getobjectbypage(Comment,page=page,where=where,args=args)
    if op == '2':  
        obj=yield from getobjectbypage(Comment,page=page,where=where,args=args)
    return {
    'page':obj['page'],
    'mentions':obj['items'],
    'newsnum':newsnum
    }

@get('/mentions/getlike')
def getlikementions(request,*,op,page='1'):
    selfUser=request.__user__
    if selfUser is None:
        raise APIPermissionError('请登录')
    # args要用list装起来
    blogs=yield from Blog.findAll('user_id=?',[selfUser.id])
    blog_ids= [blog.id for blog in blogs]
    where='news=1 and blog_id in ('+','.join(len(blog_ids)*'?')+')'
    newsnum= yield from Appreciate.findNumber('count(id)',where,blog_ids)
    if op =='1':
        where='blog_id in ('+','.join(len(blog_ids)*'?')+')'
        obj=yield from getobjectbypage(Appreciate,page=page,where=where,args=blog_ids)
    if op == '2':  
        obj=yield from getobjectbypage(Appreciate,page=page,where=where,args=blog_ids)
    return {
    'page':obj['page'],
    'mentions':obj['items'],
    'newsnum':newsnum
    }
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
    if blog is None:
        raise APIValueError('博文不存在')
    tag_relations = yield from Tag_relation.findAll('blog_id=?',blog.id)
    tagnames = [tag_relation.tag_name for tag_relation in tag_relations]
    blog['tagnames']=tagnames
    return blog

@post('/api/blogs')
def api_create_blog(request, *, name,summary,content,image,tagnames,atNameAndIds):
    user=request.__user__
    if request.__user__ is None:
        raise APIPermissionError('请登录后再写博文')
    if not name or not name.strip():
        raise APIValueError('name', 'name cannot be empty.')
    if not content or not content.strip():
        raise APIValueError('content', 'content cannot be empty.')
    userid=user.id
    argsList={'user_id':userid,'user_name':user.name,'user_image':user.image,'name':name.strip(),'content':content.strip()}
    if summary:
        argsList['summary']=summary
    if image:
        argsList['image']=image
    blog = Blog(**argsList)
    yield from blog.save()
    for tagname in tagnames:
        tag=yield from Tag.find(tagname,'name',userid,'user_id')
        if tag is None:
            tag=Tag(name=tagname,user_id=userid)
            yield from tag.save()
        else:
            tag.num=tag.num+1
            yield from tag.update()
        tag_relation=Tag_relation(tag_name=tagname,blog_id=blog.id,user_id=userid)
        yield from tag_relation.save()
    for atNameAndId in atNameAndIds:
        toUser = yield from User.find(atNameAndId['name'],'name')
        if toUser:
            atwho = Atwho(id=atNameAndId['uuid'],from_user_id=userid,from_user_name=user.name,to_user_id=toUser.id,to_user_name=toUser.name,blog_id=blog.id,blog_name=blog.name)
            yield from atwho.save()
    return {'id':blog.id}

@post('/api/blogs/{id}')
def api_update_blog(id, request, *, name, summary, content,image,tagnames,atNameAndIds):
    blog = yield from Blog.find(id)
    selfUser=request.__user__
    if not request.__user__.admin and selfUser.id != blog.user_id :
        raise APIPermissionError('you have not permission')
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
    oldTag_relations = yield from Tag_relation.findAll('blog_id=?',blog.id)
    for oldTag_relation in oldTag_relations:
       yield from oldTag_relation.remove()
       tag=yield from Tag.find(oldTag_relation.tag_name,'name')
       if tag:
            tag.num=tag.num-1
            if tag.num==0:
                yield from tag.remove()
            else:
                yield from tag.update()
    for tagname in tagnames:
        tag=yield from Tag.find(tagname,'name',selfUser.id,'user_id')
        if tag is None:
            tag=Tag(name=tagname,user_id=selfUser.id)
            yield from tag.save()
        else:
            tag.num=tag.num+1
            yield from tag.update()
        tag_relation=Tag_relation(tag_name=tagname,blog_id=blog.id,user_id=selfUser.id)
        yield from tag_relation.save()

    for atNameAndId in atNameAndIds:
        toUser = yield from User.find(atNameAndId['name'],'name')
        if toUser:
            oldAtWho = yield from Atwho.find(atNameAndId['uuid'])
            if oldAtWho is None:
                atwho = Atwho(id=atNameAndId['uuid'],from_user_id=selfUser.id,from_user_name=selfUser.name,to_user_id=toUser.id,to_user_name=toUser.name,blog_id=blog.id,blog_name=blog.name)
                yield from atwho.save()
    return blog

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
    tag_relations = yield from Tag_relation.findAll('blog_id=?',id)
    if len(tag_relations):
        for tag_relation in tag_relations:
            yield from tag_relation.remove()
            tag = yield from Tag.find(tag_relation.tag_name,'name',blog.user_id,'user_id')
            if tag:
                tag.num = tag.num - 1
                if tag.num ==0:
                    yield from tag.remove()
                else:
                    yield from tag.update()
    return dict(id=id)

@get('/getmentions')
def getmentions(request,*,term):
    selfUser = request.__user__
    if selfUser is None:
        raise APIPermissionError('登录才有提示功能')
    str = term+'%'
    filterfollowings = yield from Follow.findAll('from_user_id=? and to_user_name like ?',[selfUser.id,str],orderBy='created_at desc',limit=(0,9))
    if len(filterfollowings) ==0:
        return {'message':'not found'}
    filterfonames = [filterfollowing.to_user_name for filterfollowing in filterfollowings]
    return {'usernames':filterfonames}
    
@get('/turnold/{name}')
def turnold(name,request,*,id):
    options={'atwho':Atwho,'conversation':Conversation,'comment':Comment,'follow':Follow,'like':Appreciate}
    Mention = options.get(name,None)
    if Mention is None: 
        raise APIError('404')
    selfUser=request.__user__
    if selfUser is None:
        return{'message':0}
    mention=yield from Mention.find(id)
    if Mention == Comment or Mention==Appreciate:
        blog = yield from Blog.find(mention['blog_id'],'id')
        if blog.get('user_id',None)!= selfUser.id:
            return{'message':0}
    else:
        if mention.get('to_user_id',None) != selfUser.id :
            return{'message':0}
    mention.news=0
    yield from mention.update()
    return {'message':1}

@get('/clearallnews/{name}')
def clearallnews(name,request):
    options={'atwho':Atwho,'conversation':Conversation,'comment':Comment,'follow':Follow,'like':Appreciate}
    Mention = options.get(name,None)
    if Mention is None: 
        raise APIError('404')
    selfUser=request.__user__
    if selfUser is None:
        return{'message':0}
    if Mention == Comment or Mention==Appreciate:
        blogs = yield from Blog.findAll('user_id=?',selfUser.id)
        blog_ids= [blog.id for blog in blogs]
        where='news=1 and blog_id in ('+','.join(len(blog_ids)*'?')+')'
        items = yield from Mention.findAll(where,blog_ids)
        if len(items):
            for item in items:
                item.news=0
                yield from item.update()
    else:
        mentions=yield from Mention.findAll('to_user_id=? and news=?',[selfUser.id,1])
        for mention in mentions:
            mention.news=0
            yield from mention.update()
    return {'message':1}

@get('/getarticles')
def getarticles(*,id,page):
    obj=yield from getobjectbypage(Blog,where='user_id=?',args=[id],page=page)
    return {
    'articles':obj['items'],
    'page':obj['page']
    }

@get('/getallnews')
def getallnews(request):
    selfUser = request.__user__
    if selfUser is None:
        return {'message':0}
    dianews= yield from Conversation.findNumber('count(id)','to_user_id=?',[selfUser.id])
    atnews= yield from Atwho.findNumber('count(id)','to_user_id=?',[selfUser.id])
    follownews= yield from Follow.findNumber('count(id)','to_user_id=?',[selfUser.id])
    allcount=dianews+atnews+follownews
    return {
    'dianews':dianews,
    'atnews':atnews,
    'follownews':follownews,
    'allcount':allcount
    }