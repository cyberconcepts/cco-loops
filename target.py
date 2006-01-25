#
#  Copyright (c) 2006 Helmut Merz helmutm@cy55.de
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
Adapter classes (proxies, in fact), for providing access to concepts and
resources e.g. from forms that are called on view/node objects.

$Id$
"""

from zope.app import zapi
from zope.cachedescriptors.property import Lazy
from zope.component import adapts
from zope.interface import implements

from loops.interfaces import IResource, IDocument, IMediaAsset
from loops.interfaces import IView


class ResourceProxy(object):

    adapts(IView)

    def getTitle(self): return self.target.title
    def setTitle(self, title): self.title = title
    title = property(getTitle, setTitle)

    def setContentType(self, contentType):
        self.target._contentType = contentType
    def getContentType(self): return self.target.contentType
    contentType = property(getContentType, setContentType)

    def __init__(self, context):
        self.context = context

    @Lazy
    def target(self):
        return self.context.target
        

class DocumentProxy(ResourceProxy):

    implements(IDocument)

    def setData(self, data): self.target.data = data
    def getData(self): return self.target.data
    data = property(getData, setData)


class MediaAssetProxy(ResourceProxy):

    implements(IMediaAsset)

    def setData(self, data): self.target.data = data
    def getData(self): return self.target.data
    data = property(getData, setData)

