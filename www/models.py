#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''
Models for user, blog, comment.
'''

__author__ = 'Michael Liao'

import time, uuid

from orm import Model, StringField, BooleanField, FloatField, TextField,SmallIntField,IntField

def next_id():
    return '%015d%s000' % (int(time.time() * 1000), uuid.uuid4().hex)

class User(Model):
    __table__ = 'users'
    id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    email = StringField(ddl='varchar(50)')
    passwd = StringField(ddl='varchar(50)')
    admin = BooleanField()
    name = StringField(ddl='varchar(50)')
    image = StringField(ddl='varchar(500)')
    created_at = FloatField(default=time.time)
    following_num = SmallIntField(default=0)
    follower_num = IntField(default=0)
    review_num = SmallIntField(default=0)

class Blog(Model):
    __table__ = 'blogs'
    id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    user_id = StringField(ddl='varchar(50)')
    user_name = StringField(ddl='varchar(50)')
    user_image = StringField(ddl='varchar(500)')
    image = StringField(ddl='varchar(500)',default='')
    read_num = IntField()
    like_num = SmallIntField()
    name = StringField(ddl='varchar(50)')
    summary = StringField(ddl='varchar(200)',default='')
    content = TextField()
    created_at = FloatField(default=time.time)
    update_at = FloatField()

class Comment(Model):
    __table__ = 'comments'

    id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    blog_id = StringField(ddl='varchar(50)')
    user_id = StringField(ddl='varchar(50)')
    agree_num = SmallIntField(default=0)
    user_name = StringField(ddl='varchar(50)')
    user_image = StringField(ddl='varchar(500)')
    content = TextField()
    created_at = FloatField(default=time.time)
    update_at = FloatField()

class Follow(Model):
    __table__ = 'follows'
    id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    from_user_id = StringField(ddl='varchar(50)')
    to_user_id = StringField(ddl='varchar(50)')
    created_at = FloatField(default=time.time)


class Appreciate(Model):
    __table__ = 'appreciates'
    id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    user_id = StringField(ddl='varchar(50)')
    blog_id = StringField(ddl='varchar(50)')
    created_at = FloatField(default=time.time)

class Agree(Model):
    __table__ = 'agrees'
    id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    user_id = StringField(ddl='varchar(50)')
    comment_id = StringField(ddl='varchar(50)')
    state = BooleanField()
    created_at = FloatField(default=time.time)

class Conversation(Model):
    __table__ = 'conversations'
    id = StringField(primary_key=True, default=next_id, ddl='varchar(50)')
    from_user_id = StringField(ddl='varchar(50)')
    to_user_id = StringField(ddl='varchar(50)')
    content = TextField()
    created_at = FloatField(default=time.time)
    news = BooleanField()