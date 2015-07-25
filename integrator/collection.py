#
#  Copyright (c) 2012 Helmut Merz helmutm@cy55.de
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
"""

from datetime import datetime
from logging import getLogger
import os, re, stat

from zope.app.container.interfaces import INameChooser
from zope.app.container.contained import ObjectRemovedEvent
from zope.cachedescriptors.property import Lazy
from zope import component
from zope.component import adapts
from zope.contenttype import guess_content_type
from zope.event import notify
from zope.lifecycleevent import ObjectModifiedEvent
from zope.interface import implements, Attribute
from zope.schema.interfaces import IField
from zope.traversing.api import getName, getParent

from cybertools.meta.interfaces import IOptions
from cybertools.text import mimetypes
from cybertools.typology.interfaces import IType
from loops.common import AdapterBase, adapted, normalizeName
from loops.interfaces import IResource, IConcept
from loops.integrator.interfaces import IExternalCollection
from loops.integrator.interfaces import IExternalCollectionProvider
from loops.resource import Resource
from loops.setup import addAndConfigureObject
from loops.type import TypeInterfaceSourceList
from loops.versioning.interfaces import IVersionable


TypeInterfaceSourceList.typeInterfaces += (IExternalCollection,)


class ExternalCollectionAdapter(AdapterBase):
    """ A concept adapter for accessing an external collection.
        May delegate access to a named utility.
    """

    implements(IExternalCollection)
    adapts(IConcept)

    _adapterAttributes = AdapterBase._adapterAttributes + (
                            'exclude', 'newResources', 'updateMessage')
    _contextAttributes = list(IExternalCollection) + list(IConcept)

    newResources = None
    updateMessage = None

    def getExclude(self):
        return getattr(self.context, '_exclude', None) or []
    def setExclude(self, value):
        self.context._exclude = value
    exclude = property(getExclude, setExclude)

    def update(self):
        existing = self.context.getResources()
        old = dict((adapted(obj).externalAddress, obj) for obj in existing)
        versions = set()
        if self.useVersioning:
            for obj in old.values():
                for vaddr, vobj, vid in self.getVersions(obj):
                    print '###', vaddr, vobj, vid
                    versions.add(vaddr)
        new = []
        oldFound = []
        provider = component.getUtility(IExternalCollectionProvider,
                                        name=self.providerName or '')
        #print '*** old', old, versions, self.lastUpdated
        for addr, mdate in provider.collect(self):
            #print '***', addr, mdate
            if addr in versions:
                continue
            if addr in old:
                # may be it would be better to return a file's hash
                # for checking for changes...
                oldFound.append(addr)
                if self.lastUpdated is None or (mdate and mdate > self.lastUpdated):
                    obj = old[addr]
                    # update settings and regenerate scale variant for media asset
                    adobj = adapted(obj)
                    directory = provider.getDirectory(self)
                    adobj.storageParams=dict(subdirectory=directory)
                    adobj.request = self.request
                    adobj.externalAddress = addr
                    # collect error information
                    if adobj.processingErrors:
                        message = self.updateMessage or u''
                        message += u'<br />'.join(adobj.processingErrors)
                        self.updateMessage = message
                    # force reindexing
                    notify(ObjectModifiedEvent(obj))
            else:
                new.append(addr)
        if new:
            self.newResources = provider.createExtFileObjects(self, new)
            for r in self.newResources:
                self.context.assignResource(r)
        for addr in old:
            if str(addr) not in oldFound:
                # not part of the collection any more
                # TODO: only remove from collection but keep object?
                self.remove(old[addr])
        for r in self.context.getResources():
            adobj = adapted(r)
            if self.metaInfo != adobj.metaInfo and (
                                    not adobj.metaInfo or self.overwriteMetaInfo):
                    adobj.metaInfo = self.metaInfo
        self.lastUpdated = datetime.today()

    def clear(self):
        for obj in self.context.getResources():
            self.remove(obj)

    def remove(self, obj):
        del self.resourceManager[getName(obj)]
        notify(ObjectRemovedEvent(obj))
        getLogger('loops.integrator.collection').info(
                        'object removed: %s.' % getName(obj))

    @Lazy
    def resourceManager(self):
        return self.context.getLoopsRoot().getResourceManager()

    @Lazy
    def useVersioning(self):
        if IOptions(self.context.getLoopsRoot())('useVersioning'):
            return True

    def getVersions(self, obj):
        versionable = IVersionable(obj)
        return [(adapted(v).externalAddress, v, vid)
                    #for vid, v in versionable.versions.items() if vid != '1.1']
                    for vid, v in versionable.versions.items()
                    if IVersionable(v).parent is not None]


class DirectoryCollectionProvider(object):
    """ A utility that provides access to files in a directory.
    """

    implements(IExternalCollectionProvider)

    extFileTypeMapping = {
        'image/*': 'media_asset',
        '*/*': 'extfile',
    }

    def collect(self, client):
        directory = self.getDirectory(client)
        pattern = re.compile(client.pattern or '.*')
        for path, dirs, files in os.walk(directory):
            if client.excludeDirectories:
                del dirs[:]
            if '.svn' in dirs:
                del dirs[dirs.index('.svn')]
            for ex in client.exclude:
                if ex in dirs:
                    del dirs[dirs.index(ex)]
            for f in files:
                if pattern.match(f):
                    mtime = os.stat(os.path.join(path, f))[stat.ST_MTIME]
                    yield (os.path.join(path[len(directory)+1:], f),
                           datetime.fromtimestamp(mtime))

    def createExtFileObjects(self, client, addresses, extFileTypes=None):
        if extFileTypes is None:
            cm = client.context.getLoopsRoot().getConceptManager()
            extFileTypes = dict((k, cm.get(v))
                                for k, v in self.extFileTypeMapping.items())
        container = client.context.getLoopsRoot().getResourceManager()
        directory = self.getDirectory(client)
        for addr in addresses:
            name = self.generateName(container, addr)
            title = self.generateTitle(addr)
            contentType = guess_content_type(addr,
                                    default='application/octet-stream')[0]
            extFileType = extFileTypes.get(contentType)
            if extFileType is None:
                extFileType = extFileTypes.get(contentType.split('/')[0] + '/*')
                if extFileType is None:
                    extFileType = extFileTypes['*/*']
                if extFileType is None:
                    extFileType = extFileTypes['image/*']
            if extFileType is None:
                getLogger('loops.integrator.collection.DirectoryCollectionProvider'
                            ).warn('No external file type found for %r, '
                                   'content type: %r' % (name, contentType))
            obj = addAndConfigureObject(
                            container, Resource, name,
                            title=title,
                            resourceType=extFileType,
                            storageName='fullpath',
                            storageParams=dict(subdirectory=directory),
                            contentType=contentType,
            )
            adobj = adapted(obj)
            adobj.request = client.request
            adobj.externalAddress = addr     # must be set last
            # collect error information
            if adobj.processingErrors:
                message = client.updateMessage or u''
                message += u'<br />'.join(adobj.processingErrors)
                client.updateMessage = message
            yield obj

    def getDirectory(self, client):
        baseAddress = client.baseAddress or ''
        address = client.address or ''
        return str(os.path.join(baseAddress, address))

    def generateName(self, container, name):
        name = INameChooser(container).chooseName(name, None)
        return name

    def generateTitle(self, title):
        title = os.path.split(title)[-1]
        if '.' in title:
            base, ext = title.rsplit('.', 1)
            if ext.lower() in mimetypes.extensions.values():
                title = base
        if not isinstance(title, unicode):
            try:
                title = title.decode('UTF-8')
            except UnicodeDecodeError:
                title = title.decode('CP852')
        return title
