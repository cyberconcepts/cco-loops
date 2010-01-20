#
#  Copyright (c) 2010 Helmut Merz helmutm@cy55.de
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
view class(es) for import/export.

$Id$
"""

from cStringIO import StringIO
import os
import time
from zope import component
from zope.interface import Interface, implements
from zope.app import zapi
from zope.app.pagetemplate.viewpagetemplatefile import ViewPageTemplateFile
from zope.cachedescriptors.property import Lazy
from zope.security.proxy import removeSecurityProxy
from zope.traversing.api import getName, getPath

from loops.external.base import Loader, Extractor
from loops.external.interfaces import IReader, IWriter
from loops import util


class ExportImport(object):
    """ View providing export and import functionality.
    """

    def __init__(self, context, request):
        self.context = removeSecurityProxy(context)
        self.request = request
        self.message = u''

    @Lazy
    def baseDirectory(self):
        return util.getVarDirectory(self.request)

    @Lazy
    def sitePath(self):
        return getPath(self.context)[1:].replace('/', '_')

    @Lazy
    def resourceImportDirectory(self):
        return os.path.join(self.baseDirectory, 'import', self.sitePath)

    @Lazy
    def resourceExportDirectory(self):
        return os.path.join(self.baseDirectory, 'export', self.sitePath)

    def submit(self):
        action = self.request.get('loops.action', None)
        if action:
            method = getattr(self, action, None)
            if method:
                return method()
        return False

    def export(self):
        form = self.request.form
        parents = predicates = None
        parentIds = form.get('parents')
        if parentIds:
            parentIds = [id for id in parentIds.splitlines() if id]
            parents = [self.conceptManager.get(id) for id in parentIds]
            parents = [p for p in parents if p is not None]
        predicateIds = form.get('predicates')
        if predicateIds:
            predicates = (predicateIds and [self.conceptManager[id]
                                for id in predicateIds] or None)
        changed = form.get('changed')
        includeSubconcepts = form.get('include_subconcepts')
        includeResources = form.get('include_resources')
        extractor = Extractor(self.context, self.resourceExportDirectory)
        if changed:
            changed = self.parseDate(changed)
            if changed:
                elements = extractor.extractChanged(changed, parents, predicates,
                                        includeSubconcepts, includeResources)
        elif parents:
            elements = extractor.extractForParents(parents, predicates,
                                    includeSubconcepts, includeResources)
        else:
            elements = extractor.extract()
        return self.download(elements)

    def download(self, elements):
        writer = component.getUtility(IWriter)
        f = StringIO()
        writer.write(elements, f)
        text = f.getvalue()
        f.close()
        self.setDownloadHeader(self.request, text)
        return text

    def parseDate(self, s):
        try:
            t = time.strptime(s, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            try:
                t = time.strptime(s, '%Y-%m-%d %H:%M')
            except ValueError:
                t = time.strptime(s, '%Y-%m-%d')
        return int(time.mktime(t))

    @Lazy
    def conceptManager(self):
        return  self.context.getConceptManager()

    @Lazy
    def predicates(self):
        ptype = self.conceptManager['predicate']
        hasType = self.conceptManager['hasType']
        return [dict(name=getName(p), title=p.title)
                for p in ptype.getChildren([hasType])]

    def upload(self):
        data = self.request.get('field.data', None)
        resourceImportDirectory = (self.request.get('resourceImportDirectory', None)
                                   or self.resourceImportDirectory)
        if not data:
            return False
        reader = component.getUtility(IReader)
        elements = reader.read(data)
        loader = Loader(self.context, resourceImportDirectory)
        loader.load(elements)
        self.message = u'Content uploaded and imported.'
        return False

    def setDownloadHeader(self, request, text):
        response = request.response
        response.setHeader('Content-Disposition',
                           'attachment; filename=loopscontent.dmp')
        response.setHeader('Content-Type', 'text/plain')
        response.setHeader('Content-Length', len(text))

