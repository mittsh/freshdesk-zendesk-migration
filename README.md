Migrate to Zendesk
==================

Migrate your tickets, comments/notes, status away from Freshdesk and use
the beautiful Zendesk!

Quick use
---------

Clone the repo, and open `f2z.py` with your favorite text editor.
Just change your Freshdesk and Zendesk credentials, and run the script with
Python.

```sh
python f2z.py
```

Custom fields
-------------

Both services have custom fields. Update the `custom_fields` dictionary
to migrate your fields. Keys are Freshdesk fields, values are Zendesk fields.

You can configure `custom_field_freshdesk_url`, this will set the previous
Freshdesk ticket URL into this field.

Type Migration
--------------

This will migrate Freshdesk Ticket Types into Zendesk. Pass a dictionary to
`type_migration`, keys being Freshdesk types and values Zendesk types.

Status Migration
----------------

If you're using custom statuses in Freshdesk, it will migrate them as status
and tag in Zendesk.
This will migrate Freshdesk Ticket Statuses into Zendesk. Pass a dictionary to
`status_migration`, keys being Freshdesk statuses, values are tuples of Zendesk
status and tags.

Run into a Python script
------------------------

`f2z.py` is designed so you can include it in your own Python module. Here is an example:

```python
import f2z
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
		'freshdesk_field':'4242',
	},
	custom_field_freshdesk_url='424242',
	type_migration={
		'Question':'Questions',
		'Bug':'Incidents',
		'Feature Request':'Tasks',
	},
	status_migration={
		8:('pending', 'pending-for-release',)
	}
)
f2z.migrate_all(205)
```
