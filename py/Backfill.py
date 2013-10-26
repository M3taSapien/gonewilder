#!/usr/bin/python

"""
	"Backfill" existing database data.
	Gets titles, permalinks, dates, etc from reddit.
	Overwrites existing 'bad' data with accurate data.
"""

from DB      import DB
from Reddit  import Reddit
from sys     import exit, stdout
from urllib2 import HTTPError

db = DB()
reddit = Reddit()

def backfill_users():
	q_users = '''
		select id,username
			from users
			where deleted = 0
	'''
	cur = db.conn.cursor()
	execur = cur.execute(q_users)
	ids_and_users = execur.fetchall() # Get list of users + ids
	for (userid, username) in ids_and_users:
		print 'updating %s...' % username,
		stdout.flush()
		try:
			ui = Reddit.get_user_info(username)
		except Exception, e:
			print str(e)
			continue
		q_user = '''
			update users 
				set
					created  = %d,
					username = "%s"
				where id = %d
		''' % (ui.created, ui.name, userid)
		cur.execute(q_user)
		print 'done'
	
	cur.close()

def backfill_posts():
	POSTS = {}

	(username, password) = db.get_credentials('reddit')
	reddit.login(username, password)

	cur = db.conn.cursor()
	query = '''
		select * 
			from posts
			where legacy = 1
			order by id
	'''
	execur = cur.execute(query)
	results = execur.fetchall()

	# Store existing values in dict
	for (postid, userid, title, url, subreddit, over_18, created, legacy, permalink) in results:
		postid = str(postid)
		POSTS[postid] = {
				'userid'    : userid,
				'title'     : title,
				'url'       : url,
				'subreddit' : subreddit,
				'over_18'   : over_18,
				'created'   : created,
				'legacy'    : legacy,
				'permalink' : permalink
			}

	posts_per_page = 99
	i = 0
	while i < len(results):
		ids = [str(x[0]) for x in results[i:i+posts_per_page]]
		ids.append('t3_1234')
		url = 'http://www.reddit.com/by_id/t3_%s.json' % ',t3_'.join(ids)
		try:
			posts = reddit.get(url)
		except HTTPError:
			posts = []

		for post in posts:
			post.id = str(post.id)
			if not post.id in POSTS: post.id = post.id.rjust(6, '0')
			if not post.id in POSTS: continue
			oldpost = POSTS[post.id]
			oldpost['title']     = post.title
			oldpost['url']       = post.url
			oldpost['subreddit'] = post.subreddit
			oldpost['created']   = int(post.created)
			oldpost['permalink'] = post.permalink()
			oldpost['over_18']   = int(post.over_18)
			oldpost['legacy']    = 0
			oldpost['id']        = post.id
			Reddit.debug('updating post %s by %s' % (post.id, post.author))
			update_post(oldpost)
		db.conn.commit()
		i += posts_per_page
		Reddit.debug('%d/%d - %d remaining' % (i, len(results), len(results)-i))

def update_post(post):
	query = '''
	update posts
		set
			title = ?,
			url = ?,
			subreddit = ?,
			over_18 = ?,
			created = ?,
			permalink = ?,
			legacy = 0
		where
			id = ?
	'''
	cur = db.conn.cursor()
	cur.execute(query, (post['title'], post['url'], post['subreddit'], post['over_18'],
	                    post['created'], post['permalink'], post['id']) )
	cur.close()

if __name__ == '__main__':
	backfill_users()
