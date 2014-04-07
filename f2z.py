import urllib2
import base64
import json
import logging
import os
import re
import unicodedata

logger = logging.getLogger(__name__)

class F2ZFreshTicketDoesNotExist(Exception):
	pass
class F2ZFreshUserDoesNotExist(Exception):
	pass

class F2Z(object):
	def __init__(
			self,
			freshdesk_company,
			freshdesk_username,
			freshdesk_pw,
			zendesk_company,
			zendesk_username,
			zendesk_pw,
			freshdesk_cache_dir=None,
			custom_fields={},
			custom_field_freshdesk_url=None,
			type_migration=None,
			status_migration=None,
		):

		# Freshdesk API
		self.freshdesk_company = freshdesk_company
		self.freshdesk_base_url = u'https://{company}.freshdesk.com'.format(
			company=freshdesk_company
		)
		self.freshdesk_header_auth = 'Basic {0}'.format(
			base64.encodestring('{0}:{1}'.format(
				freshdesk_username,
				freshdesk_pw,
			)).replace('\n', '')
		)
		self.freshdesk_cache_dir = freshdesk_cache_dir

		# Zendesk API
		self.zendesk_company = zendesk_company
		self.zendesk_base_url = u'https://{company}.zendesk.com'.format(
			company=zendesk_company
		)
		self.zendesk_header_auth = 'Basic {0}'.format(
			base64.encodestring('{0}:{1}'.format(
				zendesk_username,
				zendesk_pw,
			)).replace('\n', '')
		)

		# Custom Fields
		self.custom_fields = custom_fields
		self.custom_field_freshdesk_url = custom_field_freshdesk_url

		# Type Migration
		self.type_migration = type_migration

		# Status Migration
		self.status_migration = status_migration

	def slugify(self, value):
		_slugify_strip_re = re.compile(r'[^\w\s-]')
		_slugify_hyphenate_re = re.compile(r'[-_\s]+')
		# make sure we have a unicode string
		e = unicode(value)
		# converts to ascii
		e = unicodedata.normalize('NFKD', e).encode('ascii', 'ignore')
		# remove non-alphanumeric or non-ascii characters
		e = _slugify_strip_re.sub('', e)
		# lower the case
		e = e.lower()
		# replace spaces and underscores by hyphens
		e = _slugify_hyphenate_re.sub('-', e)
		# strip (remove dashes beginning and end)
		e = e.strip('-')
		return e

	def freshdesk_get_ticket(self, fd_tid):
		cache_filepath = None
		if self.freshdesk_cache_dir:
			cache_filepath = os.path.join(
				self.freshdesk_cache_dir,
				'ticket_{0}.json'.format(fd_tid),
			)
			if os.path.isfile(cache_filepath):
				logger.info('Retrieved Freshdesk Ticket #{0} from cache'.format(
					fd_tid
				))
				with open(cache_filepath, 'r') as f:
					return json.loads(f.read())

		request = urllib2.Request(
			url=self.freshdesk_base_url + '/helpdesk/tickets/{0}.json'.format(
				fd_tid
			),
			headers={
				'Authorization':self.freshdesk_header_auth
			}
		)
		response = urllib2.urlopen(request)
		d = json.loads(response.read())
		if not d.has_key('helpdesk_ticket'):
			logger.error('Cannot fetch Freshdesk Ticket #{0}: {1}'.format(
				fd_tid,
				json.dumps(d),
			))
			raise F2ZFreshTicketDoesNotExist
		if cache_filepath:
			with open(cache_filepath, 'w') as f:
				f.write(json.dumps(d['helpdesk_ticket']))
		logger.info('Fetched Freshdesk Ticket #{0}'.format(
			fd_tid
		))
		return d['helpdesk_ticket']

	def freshdesk_get_user(self, fd_uid):
		cache_filepath = None
		if self.freshdesk_cache_dir:
			cache_filepath = os.path.join(
				self.freshdesk_cache_dir,
				'user_{0}.json'.format(fd_uid),
			)
			if os.path.isfile(cache_filepath):
				logger.info('Retrieved Freshdesk User #{0} from cache'.format(
					fd_uid
				))
				with open(cache_filepath, 'r') as f:
					return json.loads(f.read())

		request = urllib2.Request(
			url=self.freshdesk_base_url + '/contacts/{0}.json'.format(fd_uid),
			headers={
				'Authorization':self.freshdesk_header_auth
			}
		)
		response = urllib2.urlopen(request)
		d = json.loads(response.read())
		if not d.has_key('user'):
			logger.error('Cannot fetch Freshdesk User #{0}: {1}'.format(
				fd_uid,
				json.dumps(d),
			))
			raise F2ZFreshUserDoesNotExist
		if cache_filepath:
			with open(cache_filepath, 'w') as f:
				f.write(json.dumps(d['user']))
		logger.info('Fetched Freshdesk User #{0}'.format(
			fd_uid
		))
		return d['user']

	def zendesk_post_ticket(self, fd_ticket):

		fd_user = self.freshdesk_get_user(fd_ticket['requester_id'])
		fd_url = 'http://{0}.freshdesk.com/helpdesk/tickets/{1}'.format(
			self.freshdesk_company,
			fd_ticket['display_id'],
		)

		d = {
			'subject':fd_ticket['subject'],
			'description':fd_ticket['description'],
			'created_at':fd_ticket['created_at'],
			'updated_at':fd_ticket['updated_at'],
			'requester':{
				'name':fd_user['name'],
				'email':fd_user['email'],
			}
		}

		# Tags
		d['tags'] = [
			self.slugify(fd_ticket['ticket_type']),
			'freshdesk-import',
		]

		# Status
		status = int(fd_ticket['status'])
		if status == 1:
			zd_status = 'new'
		elif status == 2:
			zd_status = 'open'
		elif status == 3:
			zd_status = 'pending'
		if status == 4:
			zd_status = 'solved'
		if status == 5:
			zd_status = 'solved'
		else:
			if self.status_migration and self.status_migration.has_key(status):
				zd_status = self.status_migration[status][0]
				d['tags'].append(
					self.slugify(self.status_migration[status][1])
				)
			else:
				zd_status = 'open'
		# If Solved or Closed
		if status == 4 or status == 5:
			d['solved_at'] = fd_ticket['updated_at']
		# Set all tickets to new and change status after
		d['status'] = 'new'

		# Priority
		priority = int(fd_ticket['priority'])
		if priority == 1:
			d['priority'] = 'low'
		elif priority == 2:
			d['priority'] = 'normal'
		elif priority == 3:
			d['priority'] = 'high'
		elif priority == 4:
			d['priority'] = 'urgent'
		else:
			d['priority'] = 'low'

		# Custom Fields (and Freshdesk ticket URL)
		custom_fields = [{
			'id':zd_field,
			'value':fd_ticket['custom_field'][fd_field],
		} for (fd_field, zd_field,) in self.custom_fields.iteritems()]
		if self.custom_field_freshdesk_url:
			custom_fields.append({
				'id':self.custom_field_freshdesk_url,
				'value':fd_url,
			})
		d['custom_fields'] = custom_fields

		# Type
		if self.type_migration:
			try:
				d['type'] = self.type_migration[fd_ticket['ticket_type']]
			except:
				logger.warn('No ticket type migration for {0}'.format(
					fd_ticket['ticket_type']
				))

		# Send POST Request
		request = urllib2.Request(
			url=self.zendesk_base_url + '/api/v2/tickets.json',
			data=json.dumps({
				'ticket':d,
			}),
			headers={
				'Authorization':self.zendesk_header_auth,
				'Content-Type':'application/json',
			}
		)
		try:
			response = urllib2.urlopen(request)
		except urllib2.HTTPError as e:
			logger.error(e.read())
		else:
			ticket_url = response.info()['Location']
			logger.info('Ticket POSTed to Zendesk: HTTP {0}: {1}'.format(
				response.getcode(),
				response.info()['Location'],
			))
			zd_ticket = json.loads(response.read())

		# Updates / Comments
		updates = []
		for note in fd_ticket['notes']:
			note = note['note']
			comment = {
				'public':not note['private'],
				'body':note['body'],
			}
			if int(note['user_id']) == int(fd_ticket['requester_id']):
				comment['author_id'] = zd_ticket['ticket']['requester_id']
			updates.append((comment, None,))
		# Last Comment for Migration and Status
		updates.append(({
			'public':False,
			'body':u'''Ticket migrated from Freshdesk (#{id}): {url}
Created at: {created_at}
Updated at: {updated_at}
Type: {ticket_type}
Source: {source_name}
Status: {status}
'''.format(
				id=fd_ticket['display_id'],
				url=fd_url,
				created_at=fd_ticket['created_at'],
				updated_at=fd_ticket['updated_at'],
				ticket_type=fd_ticket['ticket_type'],
				source_name=fd_ticket['source_name'],
				status=zd_status,
			)
		}, zd_status,))

		# Send PUT Requests for Comments
		for (comment, status,) in updates:
			tk = {
				'comment':comment,
			}
			if status:
				tk['status'] = status
			request = urllib2.Request(
				url=ticket_url,
				data=json.dumps({
					'ticket':tk,
				}),
				headers={
					'Authorization':self.zendesk_header_auth,
					'Content-Type':'application/json',
				}
			)
			request.get_method = lambda: 'PUT'
			try:
				response = urllib2.urlopen(request)
			except urllib2.HTTPError as e:
				logger.error(e.read())
			else:
				logger.info('Ticket PUT (Comment Added): HTTP {0}'.format(
					response.getcode(),
				))
				d = json.loads(response.read())

	def migrate_ticket(self, fd_tid):
		logger.info('Migrating Freshdesk Ticket ID #{0}'.format(fd_tid))
		fd_ticket = self.freshdesk_get_ticket(fd_tid)
		self.zendesk_post_ticket(fd_ticket)

	def migrate_all(self, ticket_max):
		fail = 0
		success = 0
		for i in xrange(ticket_max):
			fd_tid = i + 1
			try:
				self.migrate_ticket(fd_tid)
			except Exception as e:
				fail += 1
				logger.error('Failed ticket migration #{0}'.format(fd_tid))
				logger.exception(e)
			else:
				success += 1

		logger.info('Migrated {0} tickets and {1} fails'.format(
			success,
			fail,
		))

if __name__ == '__main__':
	freshdesk_company = 'fd-company'
	freshdesk_username = 'email@fd-company.com'
	freshdesk_pw = 'password'

	zendesk_company = 'zd-company'
	zendesk_username = 'email@zd-company.com'
	zendesk_pw = 'password'

	logger.setLevel(logging.DEBUG)
	ch = logging.StreamHandler()
	ch.setLevel(logging.DEBUG)
	logger.addHandler(ch)

	f2z = F2Z(
		freshdesk_company=freshdesk_company,
		freshdesk_username=freshdesk_username,
		freshdesk_pw=freshdesk_pw,
		zendesk_company=zendesk_company,
		zendesk_username=zendesk_username,
		zendesk_pw=zendesk_pw,
		freshdesk_cache_dir=os.path.join(
			os.path.dirname(__file__),
			'fcache',
		),
		custom_fields={
			'github_ticket_url_96745':'23732372',
		},
		custom_field_freshdesk_url='23732452',
		type_migration={
			'Question':'Questions',
			'Bug':'Incidents',
			'License Issue':'Problems',
			'Feature Request':'Tasks',
			'Nice Tweet':'Problems',
		},
		status_migration={
			8:('pending', 'pending-on-gitub',)
		}
	)
	# f2z.migrate_ticket(77)
	f2z.migrate_all(205)
