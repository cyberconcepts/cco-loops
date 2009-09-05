#
#  Copyright (c) 2007 Helmut Merz helmutm@cy55.de
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

"""
Concept adapter(s) for external collections, e.g. a directory in the
file system.

$Id$
"""

from datetime import datetime
import email
from logging import getLogger
import os
import time

from zope.app.container.interfaces import INameChooser
from zope.cachedescriptors.property import Lazy
from zope import component
from zope.component import adapts
from zope.event import notify
from zope.lifecycleevent import ObjectCreatedEvent, ObjectModifiedEvent
from zope.event import notify
from zope.interface import implements
from zope.traversing.api import getName, getParent

from loops.common import AdapterBase, adapted
from loops.interfaces import IResource, IConcept
from loops.integrator.interfaces import IExternalCollectionProvider
from loops.integrator.mail.system import IMAP4
from loops.resource import Resource
from loops.setup import addAndConfigureObject


class IMAPCollectionProvider(object):
    """ A utility that provides access to an IMAP folder.
    """

    implements(IExternalCollectionProvider)

    def collect(self, client):
        client._collectedObjects = {}
        hostName = client.baseAddress
        if hostName in ('', None, 'localhost'):
            hostName = os.uname()[1]
        baseId = 'imap://%s@%s' % (client.userName, hostName)
        imap = IMAP4(client.baseAddress)
        imap.login(client.userName, client.password)
        mailbox = 'INBOX'
        addr = client.address
        if addr:
            mailbox = mailbox + '.' + addr.replace('/', '.')
        imap.select(mailbox)
        type, data = imap.search(None, 'ALL')
        for num in data[0].split():
            type, data = imap.fetch(num, '(RFC822)')
            raw_msg = data[0][1]
            msg = email.message_from_string(raw_msg)
            msgId = msg['Message-ID'].replace('<', '').replace('>', '')
            externalAddress = '/'.join((baseId, msgId))
            #mtime = datetime.today()
            client._collectedObjects[externalAddress] = msg
            yield externalAddress, None

    def createExtFileObjects(self, client, addresses, extFileTypes=None):
        loopsRoot = client.context.getLoopsRoot()
        container = loopsRoot.getResourceManager()
        contentType = 'text/plain'
        resourceType = loopsRoot.getConceptManager()['email']
        for addr in addresses:
            msg = client._collectedObjects[addr]
            title = msg['Subject']
            sender = msg['From']
            receiver = msg['To']
            raw_date = msg['Date'].rsplit(' ', 1)[0]
            fmt = '%a,  %d %b %Y %H:%M:%S'
            date = datetime(*(time.strptime(raw_date, fmt)[0:6]))
            parts = self.getPayload(msg, {})
            if 'html' in parts:
                text = parts['html']
                ct = 'text/html'
            else:
                text = parts.get('plain') or u'No message found.'
                ct = 'text/plain'
            obj = Resource(title)
            name = INameChooser(container).chooseName(None, obj)
            container[name] = obj
            obj.resourceType = resourceType
            adObj = adapted(obj)
            adObj.externalAddress = addr
            adObj.contentType = ct
            adObj.sender = sender
            adObj.receiver = receiver
            adObj.date = date
            adObj.data = text
            notify(ObjectCreatedEvent(obj))
            notify(ObjectModifiedEvent(obj))
            yield obj

    def getPayload(self, msg, parts):
        def getCharset(ct):
            if 'charset=' in ct:
                cs = ct.split('charset=', 1)[1]
                if ';' in cs:
                    cs = cs.split(';', 1)[0]
                return cs.replace('"', '')
        if msg.is_multipart():
            for part in msg.get_payload():
                self.getPayload(part, parts)
        else:
            ct = msg['Content-Type']
            if ct and ct.startswith('text/html'):
                parts['html'] = msg.get_payload(decode=True).decode(getCharset(ct))
            elif ct and ct.startswith('text/plain'):
                parts['plain'] = msg.get_payload(decode=True).decode(getCharset(ct))
        return parts
