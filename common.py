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
Common stuff.

$Id$
"""

from zope.app import zapi
from zope.dublincore.interfaces import IZopeDublinCore
from zope.dublincore.annotatableadapter import ZDCAnnotatableAdapter
from zope.dublincore.zopedublincore import ScalarProperty
from zope.component import adapts
from zope.interface import implements
from zope.cachedescriptors.property import Lazy
from loops.interfaces import ILoopsObject, IConcept, IResource
from loops.interfaces import IResourceAdapter


# type interface adapters

class AdapterBase(object):
    """ (Mix-in) Class for concept adapters that provide editing of fields
        defined by the type interface.
    """

    adapts(IConcept)

    _attributes = ('context', '__parent__', )
    _schemas = list(IConcept)

    def __init__(self, context):
        self.context = context # to get the permission stuff right
        self.__parent__ = context

    def __getattr__(self, attr):
        self.checkAttr(attr)
        return getattr(self.context, '_' + attr, None)

    def __setattr__(self, attr, value):
        if attr in self._attributes:
            object.__setattr__(self, attr, value)
        else:
            self.checkAttr(attr)
            setattr(self.context, '_' + attr, value)

    def checkAttr(self, attr):
        if attr not in self._schemas:
            raise AttributeError(attr)

    def __eq__(self, other):
        return self.context == other.context


class ResourceAdapterBase(AdapterBase):

    adapts(IResource)

    _schemas = list(IResourceAdapter)


# other adapters

class LoopsDCAdapter(ZDCAnnotatableAdapter):

    implements(IZopeDublinCore)
    adapts(ILoopsObject)

    def __init__(self, context):
        self.context = context
        super(LoopsDCAdapter, self).__init__(context)

    def Title(self):
        return super(LoopsDCAdapter, self).title or self.context.title
    def setTitle(self, value):
        ScalarProperty(u'Title').__set__(self, value)
    title = property(Title, setTitle)


