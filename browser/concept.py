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
Definition of the concept view classes.

$Id$
"""

from itertools import groupby
from zope import interface, component, schema
from zope.app import zapi
from zope.app.catalog.interfaces import ICatalog
from zope.lifecycleevent import ObjectCreatedEvent, ObjectModifiedEvent
from zope.app.container.contained import ObjectRemovedEvent
from zope.app.form.browser.interfaces import ITerms
from zope.app.form.interfaces import IDisplayWidget
from zope.app.pagetemplate import ViewPageTemplateFile
from zope.app.security.interfaces import IUnauthenticatedPrincipal
from zope.cachedescriptors.property import Lazy
from zope.dottedname.resolve import resolve
from zope.event import notify
from zope.formlib.form import EditForm, FormFields, setUpEditWidgets
from zope.formlib.namedtemplate import NamedTemplate
from zope.interface import implements
from zope.publisher.interfaces import BadRequest
from zope.publisher.interfaces.browser import IBrowserRequest
from zope.schema.interfaces import IIterableSource
from zope.security.proxy import removeSecurityProxy
from zope.traversing.api import getName

from cybertools.browser.action import actions
from cybertools.composer.interfaces import IInstance
from cybertools.composer.schema.interfaces import ISchemaFactory
from cybertools.typology.interfaces import IType, ITypeManager
from cybertools.util.jeep import Jeep
from loops.browser.common import EditForm, BaseView, LoopsTerms, conceptMacrosTemplate
from loops.common import adapted
from loops.concept import Concept, ConceptTypeSourceList, PredicateSourceList
from loops.i18n.browser import I18NView
from loops.interfaces import IConcept, IConceptSchema, ITypeConcept, IResource
from loops import util
from loops.util import _
from loops.versioning.util import getVersion


class ConceptEditForm(EditForm, I18NView):
    """ Classic-style (zope.formlib-based) form for editing concepts.
    """

    #@Lazy  # zope.formlib does not issue a redirect after changes, so that
            # it tries to redisplay the old form even after a type change that
            # changes the set of available attributes. So the typeInterface
            # must be recalculated e.g. after an update of the context object.
    @property
    def typeInterface(self):
        return IType(self.context).typeInterface

    @Lazy
    def title(self):
        return adapted(self.context, self.languageInfo).title

    @property
    def form_fields(self):
        typeInterface = self.typeInterface
        if typeInterface is None:
            fields = FormFields(IConcept)
        elif 'title' in typeInterface:  # new type interface based on ConceptSchema
            f1 = FormFields(IConcept).omit('title', 'description')
            fields = FormFields(typeInterface, f1)
        else:
            fields = FormFields(IConcept, typeInterface)
        return fields

    def setUpWidgets(self, ignore_request=False):
        # TODO: get rid of removeSecurityProxy(): use ConceptSchema in interfaces
        #adapter = removeSecurityProxy(adapted(self.context, self.languageInfo))
        adapter = adapted(self.context, self.languageInfo)
        self.adapters = {self.typeInterface: adapter,
                         IConceptSchema: adapter}
        self.widgets = setUpEditWidgets(
            self.form_fields, self.prefix, self.context, self.request,
            adapters=self.adapters, ignore_request=ignore_request)
        desc = self.widgets.get('description')
        if desc:
            desc.height = 2


class ConceptRelationView(BaseView):
    """ For displaying children and resources lists, used by ConceptView.
    """

    def __init__(self, relation, request, contextIsSecond=False):
        if contextIsSecond:
            self.context = relation.second
            self.other = relation.first
        else:
            self.context = relation.first
            self.other = relation.second
        self.context = getVersion(self.context, request)
        self.predicate = relation.predicate
        self.relation = relation
        self.request = request

    @Lazy
    def adapted(self):
        return adapted(self.context, self.languageInfo)

    @Lazy
    def data(self):
        return self.instance.applyTemplate()

    @Lazy
    def instance(self):
        instance = IInstance(self.adapted)
        instance.template = self.schema
        instance.view = self
        return instance

    @Lazy
    def schema(self):
        ti = self.typeInterface or IConceptSchema
        schemaFactory = component.getAdapter(self.adapted, ISchemaFactory)
        return schemaFactory(ti, manager=self, request=self.request)

    @Lazy
    def title(self):
        return self.adapted.title or getName(self.context)

    @Lazy
    def description(self):
        return self.adapted.description

    @Lazy
    def token(self):
        return ':'.join((self.loopsRoot.getLoopsUri(self.context),
                         self.loopsRoot.getLoopsUri(self.predicate)))

    @Lazy
    def uidToken(self):
        return ':'.join((util.getUidForObject(self.context),
                         util.getUidForObject(self.predicate)))

    @Lazy
    def isProtected(self):
        return getName(self.predicate) == 'hasType'

    @Lazy
    def predicateTitle(self):
        return self.predicate.title

    @Lazy
    def predicateUrl(self):
        return zapi.absoluteURL(self.predicate, self.request)

    @Lazy
    def relevance(self):
        return self.relation.relevance

    @Lazy
    def order(self):
        return self.relation.order


class ConceptView(BaseView):

    template = ViewPageTemplateFile('concept_macros.pt')
    childViewFactory = ConceptRelationView

    @Lazy
    def macro(self):
        return self.template.macros['conceptdata']

    @Lazy
    def conceptMacros(self):
        return conceptMacrosTemplate.macros

    def __init__(self, context, request):
        super(ConceptView, self).__init__(context, request)
        cont = self.controller
        if (cont is not None and not IUnauthenticatedPrincipal.providedBy(
                                                    self.request.principal)):
            cont.macros.register('portlet_right', 'parents', title=_(u'Parents'),
                         subMacro=self.template.macros['parents'],
                         priority=20, info=self)

    @Lazy
    def adapted(self):
        return adapted(self.context, self.languageInfo)

    @Lazy
    def title(self):
        return self.adapted.title or getName(self.context)

    @Lazy
    def description(self):
        return self.adapted.description

    def fieldData(self):
        # obsolete - use getData() instead
        # TODO: change view macros accordingly
        ti = IType(self.context).typeInterface
        if not ti:
            return
        adapter = self.adapted
        for n, f in schema.getFieldsInOrder(ti):
            if n in ('title', 'description',):  # already shown in header
                continue
            value = getattr(adapter, n, '')
            if not value:
                continue
            bound = f.bind(adapter)
            widget = component.getMultiAdapter(
                                (bound, self.request), IDisplayWidget)
            widget.setRenderedValue(value)
            yield dict(title=f.title, value=value, id=n, widget=widget)

    def getData(self, omit=('title', 'description')):
        data = self.instance.applyTemplate()
        for k in omit:
            if k in data:
                del data[k]
        return data

    @Lazy
    def data(self):
        return self.getData()

    @Lazy
    def instance(self):
        instance = IInstance(self.adapted)
        instance.template = self.schema
        instance.view = self
        return instance

    @Lazy
    def schema(self):
        ti = self.typeInterface or IConceptSchema
        schemaFactory = component.getAdapter(self.adapted, ISchemaFactory)
        return schemaFactory(ti, manager=self, request=self.request)

    def getChildren(self, topLevelOnly=True, sort=True):
        cm = self.loopsRoot.getConceptManager()
        hasType = cm.getTypePredicate()
        standard = cm.getDefaultPredicate()
        rels = (self.childViewFactory(r, self.request, contextIsSecond=True)
                for r in self.context.getChildRelations(sort=None))
        if sort:
            rels = sorted(rels, key=lambda r: (r.order, r.title.lower()))
        for r in rels:
            if topLevelOnly and r.predicate == hasType:
                # only show top-level entries for type instances:
                skip = False
                for parent in r.context.getParents((standard,)):
                    if parent.conceptType == self.context:
                        skip = True
                        break
                if skip: continue
            yield r

    # Override in subclass to control what is displayd in listings:
    children = getChildren

    def childrenAlphaGroups(self):
        result = Jeep()
        rels = self.getChildren(topLevelOnly=False, sort=False)
        rels = sorted(rels, key=lambda r: r.title.lower())
        for letter, group in groupby(rels, lambda r: r.title.lower()[0]):
            letter = letter.upper()
            result[letter] = list(group)
        return result

    def childrenByType(self):
        result = Jeep()
        rels = self.getChildren(topLevelOnly=False, sort=False)
        rels = sorted(rels, key=lambda r: (r.typeTitle.lower(), r.title.lower()))
        for type, group in groupby(rels, lambda r: r.type):
            typeName = getName(type.typeProvider)
            result[typeName] = list(group)
        return result

    def parents(self):
        rels = sorted(self.context.getParentRelations(),
                      key=(lambda x: x.first.title.lower()))
        for r in rels:
            yield self.childViewFactory(r, self.request)

    def resources(self):
        rels = self.context.getResourceRelations()
        for r in rels:
            yield self.childViewFactory(r, self.request, contextIsSecond=True)

    @Lazy
    def view(self):
        context = self.context
        viewName = self.request.get('loops.viewName') or getattr(self, '_viewName', None)
        if not viewName:
            ti = IType(context).typeInterface
            # TODO: check the interface (maybe for a base interface IViewProvider)
            #       instead of the viewName attribute:
            if ti and ti != ITypeConcept and 'viewName' in ti:
                typeAdapter = ti(self.context)
                viewName = typeAdapter.viewName
        if not viewName:
            tp = IType(context).typeProvider
            if tp:
               viewName = ITypeConcept(tp).viewName
        if viewName:
            # ??? Would it make sense to use a somehow restricted interface
            #     that should be provided by the view like IQuery?
            #viewInterface = getattr(typeAdapter, 'viewInterface', None) or IQuery
            adapter = component.queryMultiAdapter((context, self.request),
                                                  name=viewName)
            if adapter is not None:
                return adapter
        #elif type provides view: use this
        return self

    def clients(self):
        from loops.browser.node import NodeView  # avoid circular import
        for node in self.context.getClients():
            yield NodeView(node, self.request)

    def getActions(self, category='object', page=None):
        t = IType(self.context)
        actInfo = t.optionsDict.get('action.' + category, '')
        actNames = [n.strip() for n in actInfo.split(',')]
        if actNames:
            return actions.get(category, actNames, view=self, page=page)
        return []


class ConceptConfigureView(ConceptView):

    def update(self):
        request = self.request
        action = request.get('action')
        if action is None:
            return True
        if action == 'create':
            self.createAndAssign()
            return True
        tokens = request.get('tokens', [])
        for token in tokens:
            parts = token.split(':')
            token = parts[0]
            if len(parts) > 1:
                relToken = parts[1]
            concept = self.loopsRoot.loopsTraverse(token)
            if action == 'assign':
                assignAs = request.get('assignAs', 'child')
                predicate = request.get('predicate') or None
                order = int(request.get('order') or 0)
                relevance = float(request.get('relevance') or 1.0)
                if predicate:
                    predicate = removeSecurityProxy(
                                    self.loopsRoot.loopsTraverse(predicate))
                if assignAs == 'child':
                    self.context.assignChild(removeSecurityProxy(concept), predicate,
                                             order, relevance)
                elif assignAs == 'parent':
                    self.context.assignParent(removeSecurityProxy(concept), predicate,
                                             order, relevance)
                elif assignAs == 'resource':
                    self.context.assignResource(removeSecurityProxy(concept), predicate,
                                             order, relevance)
                else:
                    raise(BadRequest, 'Illegal assignAs parameter: %s.' % assignAs)
            elif action == 'remove':
                predicate = self.loopsRoot.loopsTraverse(relToken)
                qualifier = request.get('qualifier')
                if qualifier == 'parents':
                    self.context.deassignParent(concept, [predicate])
                elif qualifier == 'children':
                    self.context.deassignChild(concept, [predicate])
                elif qualifier == 'resources':
                    self.context.deassignResource(concept, [predicate])
                elif qualifier == 'concepts':
                    self.context.deassignConcept(concept, [predicate])
                else:
                    raise(BadRequest, 'Illegal qualifier: %s.' % qualifier)
            else:
                    raise(BadRequest, 'Illegal action: %s.' % action)
        return True

    def createAndAssign(self):
        request = self.request
        name = request.get('create.name')
        if not name:
            raise(BadRequest, 'Empty name.')
        title = request.get('create.title', u'')
        token = self.request.get('create.type')
        type = ITypeManager(self.context).getType(token)
        factory = type.factory
        container = type.defaultContainer
        concept = removeSecurityProxy(factory(title))
        container[name] = concept
        if IConcept.providedBy(concept):
            concept.conceptType = type.typeProvider
        elif IResource.providedBy(concept):
            concept.resourceType = type.typeProvider
        notify(ObjectCreatedEvent(concept))
        notify(ObjectModifiedEvent(concept))
        assignAs = self.request.get('assignAs', 'child')
        predicate = request.get('create.predicate') or None
        if predicate:
            predicate = removeSecurityProxy(
                            self.loopsRoot.loopsTraverse(predicate))
        order = int(request.get('create.order') or 0)
        relevance = float(request.get('create.relevance') or 1.0)
        if assignAs == 'child':
            self.context.assignChild(concept, predicate, order, relevance)
        elif assignAs == 'parent':
            self.context.assignParent(concept, predicate, order, relevance)
        elif assignAs == 'resource':
            self.context.assignResource(concept, predicate, order, relevance)
        elif assignAs == 'concept':
            self.context.assignConcept(concept, predicate, order, relevance)
        else:
            raise(BadRequest, 'Illegal assignAs parameter: %s.' % assignAs)

    def search(self):
        request = self.request
        if request.get('action') != 'search':
            return []
        searchTerm = request.get('searchTerm', None)
        searchType = request.get('searchType', None)
        result = []
        if searchTerm or searchType != 'none':
            criteria = {}
            if searchTerm:
                criteria['loops_title'] = searchTerm
            if searchType:
                if searchType.endswith('*'):
                    start = searchType[:-1]
                    end = start + '\x7f'
                else:
                    start = end = searchType
                criteria['loops_type'] = (start, end)
            cat = component.getUtility(ICatalog)
            result = cat.searchResults(**criteria)
            # TODO: can this be done in a faster way?
            result = [r for r in result if r.getLoopsRoot() == self.loopsRoot]
        else:
            result = self.loopsRoot.getConceptManager().values()
        if searchType == 'none':
            result = [r for r in result if r.conceptType is None]
        return self.viewIterator(result)

    def predicates(self):
        preds = PredicateSourceList(self.context)
        terms = component.getMultiAdapter((preds, self.request), ITerms)
        for pred in preds:
            yield terms.getTerm(pred)


