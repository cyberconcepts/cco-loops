#
#  Copyright (c) 2008 Helmut Merz helmutm@cy55.de
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
Reading and writing loops objects (represented by IElement objects)
in Python function notation.

$Id$
"""

from cStringIO import StringIO
import itertools
import os
import zdaemon
from zope import component
from zope.cachedescriptors.property import Lazy
from zope.interface import implements
from zope.traversing.api import getName, getParent

from cybertools.composer.interfaces import IInstance
from cybertools.composer.schema.interfaces import ISchemaFactory
from cybertools.typology.interfaces import IType
from loops.common import adapted
from loops.external.interfaces import ILoader, IExtractor, ISubExtractor
from loops.external.element import elementTypes
from loops.interfaces import IConceptSchema, IResourceSchema
from loops.resource import Document, MediaAsset
from loops.setup import SetupManager


class Base(object):

    def __init__(self, context, resourceDirectory=None):
        self.context = context
        self.resourceDirectory = resourceDirectory

    @Lazy
    def concepts(self):
        return self.context.getConceptManager()

    @Lazy
    def resources(self):
        return self.context.getResourceManager()

    @Lazy
    def views(self):
        return self.context.getViewManager()

    @Lazy
    def typeConcept(self):
        return self.concepts.getTypeConcept()

    @Lazy
    def typePredicate(self):
        return self.concepts.getTypePredicate()


class Loader(Base, SetupManager):

    implements(ILoader)

    def __init__(self, context, resourceDirectory=None):
        super(Loader, self).__init__(context, resourceDirectory)
        self.logger = StringIO()

    def load(self, elements):
        for element in elements:
            element.execute(self)
            if element.subElements is not None:
                self.load(element.subElements)

    # TODO: care for setting attributes via Instance (Editor)
    # instead of using SetupManager methods:
    # def addConcept(self, ...):

class Extractor(Base):

    implements(IExtractor)

    def extract(self):
        return itertools.chain(self.extractTypes(),
                               self.extractConcepts(),
                               self.extractChildren(),
                               self.extractResources(),
                               self.extractResourceRelations(),
                               self.extractNodes(),
                              )

    def extractTypes(self):
        typeElement = elementTypes['type']
        for obj in self.typeConcept.getChildren([self.typePredicate]):
            data = self.getObjectData(obj)
            element = typeElement(getName(obj), obj.title, **data)
            self.provideSubElements(obj, element)
            yield element

    def extractConcepts(self):
        conceptElement = elementTypes['concept']
        typeConcept = self.typeConcept
        for name, obj in self.concepts.items():
            if obj.conceptType != typeConcept:
                data = self.getObjectData(obj)
                tp = getName(obj.conceptType)
                element = conceptElement(name, obj.title, tp, **data)
                self.provideSubElements(obj, element)
                yield element

    def extractResources(self):
        elementClass = elementTypes['resource']
        for name, obj in self.resources.items():
            data = self.getObjectData(obj, IResourceSchema)
            tp = getName(obj.resourceType)
            if isinstance(obj, Document):   # backward compatibility
                tp = 'textdocument'
            element = elementClass(name, obj.title, tp, **data)
            element.processExport(self)
            self.provideSubElements(obj, element)
            yield element

    def extractChildren(self):
        childElement = elementTypes['child']
        typePredicate = self.typePredicate
        for c in self.concepts.values():
            for r in c.getChildRelations():
                if r.predicate != typePredicate:
                    args = [getName(r.first), getName(r.second), getName(r.predicate)]
                    if r.order != 0:
                        args.append(r.order)
                    if r.relevance != 1.0:
                        args.append(r.relevance)
                    yield childElement(*args)

    def extractResourceRelations(self):
        elementClass = elementTypes['resourceRelation']
        typePredicate = self.typePredicate
        for c in self.concepts.values():
            for r in c.getResourceRelations():
                if r.predicate != typePredicate:
                    args = [getName(r.first), getName(r.second), getName(r.predicate)]
                    if r.order != 0:
                        args.append(r.order)
                    if r.relevance != 1.0:
                        args.append(r.relevance)
                    yield elementClass(*args)

    def extractNodes(self, parent=None, path=''):
        if parent is None:
            parent = self.views
        elementClass = elementTypes['node']
        for name, obj in parent.items():
            data = {}
            for attr in ('description', 'body', 'viewName'):
                value = getattr(obj, attr)
                if value:
                    data[attr] = value
            target = obj.target
            if target is not None:
                data['target'] = '/'.join((getName(getParent(target)), getName(target)))
            elem = elementClass(name, obj.title, path, obj.nodeType, **data)
            self.provideSubElements(obj, elem)
            yield elem
            childPath = path and '/'.join((path, name)) or name
            for elem in self.extractNodes(obj, childPath):
                #self.provideSubElements(obj, elem)
                yield elem

    # helper methods

    def getObjectData(self, obj, defaultInterface=IConceptSchema):
        aObj = adapted(obj)
        schemaFactory = component.getAdapter(aObj, ISchemaFactory)
        ti = IType(obj).typeInterface or defaultInterface
        schema = schemaFactory(ti, manager=self) #, request=self.request)
        instance = IInstance(aObj)
        instance.template = schema
        # TODO: use ``_not_exportable`` attribute of adapter to control export;
        # this should also convert object attributes like e.g. typeInterface
        #data = instance.applyTemplate(mode='export')
        data = instance.applyTemplate(mode='edit')
        noexp = getattr(aObj, '_noexportAttributes', ())
        for attr in noexp:
            if attr in data:
                del data[attr]
        if 'title' in data:
            del data['title']
        data['description'] = obj.description
        if not data['description']:
            del data['description']
        return data

    def provideSubElements(self, obj, element):
        for name, extractor in component.getAdapters((obj,), ISubExtractor):
            for sub in extractor.extract():
                element.add(sub)
