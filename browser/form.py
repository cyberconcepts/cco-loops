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
Classes for form presentation and processing.

$Id$
"""

from zope import component, interface, schema
from zope.component import adapts
from zope.event import notify
from zope.interface import Interface
from zope.lifecycleevent import ObjectCreatedEvent, ObjectModifiedEvent

from zope.app.container.interfaces import INameChooser
from zope.app.container.contained import ObjectAddedEvent
#from zope.app.container.contained import NameChooser
from zope.app.pagetemplate import ViewPageTemplateFile
from zope.cachedescriptors.property import Lazy
from zope.contenttype import guess_content_type
from zope.publisher.browser import FileUpload
from zope.publisher.interfaces import BadRequest
from zope.security.proxy import isinstance, removeSecurityProxy

from cybertools.ajax import innerHtml
from cybertools.browser.form import FormController
from cybertools.browser.view import popupTemplate
from cybertools.composer.interfaces import IInstance
from cybertools.composer.schema.grid.field import grid_macros
from cybertools.composer.schema.interfaces import ISchemaFactory
from cybertools.composer.schema.browser.common import schema_macros, schema_edit_macros
from cybertools.composer.schema.schema import FormState
from cybertools.stateful.interfaces import IStateful
from cybertools.typology.interfaces import IType, ITypeManager
from loops.common import adapted
from loops.concept import Concept, ConceptRelation, ResourceRelation
from loops.interfaces import IConcept, IConceptSchema, IResourceManager, IDocument
from loops.interfaces import IFile, IExternalFile, INote, ITextDocument
from loops.browser.node import NodeView
from loops.browser.concept import ConceptRelationView
from loops.i18n.browser import I18NView
from loops.query import ConceptQuery, IQueryConcept
from loops.resource import Resource
from loops.type import ITypeConcept
from loops import util
from loops.util import _
from loops.versioning.interfaces import IVersionable


# forms

class ObjectForm(NodeView):
    """ Abstract base class for resource or concept forms using Dojo dialog.
    """

    template = ViewPageTemplateFile('form_macros.pt')
    customMacro = None
    formState = FormState()     # dummy, don't update!
    isInnerHtml = True
    isPopup = False
    showAssignments = True

    def __init__(self, context, request):
        super(ObjectForm, self).__init__(context, request)
        # target is the object the view acts upon - this is not necessarily
        # the same object as the context (the object the view was created for)
        self.target = context
        #self.registerDojoForm()

    def closeAction(self, submit=False):
        if self.isPopup:
            if submit:
                return ("xhrSubmitPopup('dialog_form', '%s'); return false"
                        % (self.request.URL))
            else:
                return 'window.close()'
        if self.isInnerHtml:
            return "return closeDialog(%s);" % (submit and 'true' or 'false')
        return ''

    @Lazy
    def item(self):
        # show this view on the page instead of the node's view
        return self

    @Lazy
    def adapted(self):
        return adapted(self.target, self.languageInfo)

    @Lazy
    def typeInterface(self):
        return IType(self.target).typeInterface or ITextDocument

    @Lazy
    def fieldRenderers(self):
        renderers = dict(schema_macros.macros)
        # replace HTML edit widget with Dojo Editor
        renderers['input_html'] = self.template.macros['input_html']
        renderers['input_grid'] = grid_macros.macros['input_grid']
        return renderers

    @Lazy
    def fieldEditRenderers(self):
        return schema_edit_macros.macros

    @Lazy
    def schema(self):
        schemaFactory = ISchemaFactory(self.adapted)
        return schemaFactory(self.typeInterface, manager=self,
                             request=self.request)

    @Lazy
    def fields(self):
        return [f for f in self.schema.fields if not f.readonly]

    @Lazy
    def data(self):
        instance = self.instance
        data = instance.applyTemplate(mode='edit')
        form = self.request.form
        for k, v in data.items():
            #overwrite data with values from request.form
            if k in self.request.form:
                data[k] = form[k]
        return data

    @Lazy
    def instance(self):
        instance = IInstance(self.adapted)
        instance.template = self.schema
        instance.view = self
        return instance

    def __call__(self):
        if self.isInnerHtml:
            response = self.request.response
            #response.setHeader('Content-Type', 'text/html; charset=UTF-8')
            response.setHeader('Expires', 'Sat, 1 Jan 2000 00:00:00 GMT')
            response.setHeader('Pragma', 'no-cache')
            return innerHtml(self)
        else:
            return super(ObjectForm, self).__call__()

    @Lazy
    def defaultPredicate(self):
        return self.loopsRoot.getConceptManager().getDefaultPredicate()

    @Lazy
    def defaultPredicateUid(self):
        return util.getUidForObject(self.defaultPredicate)

    @Lazy
    def typeManager(self):
        return ITypeManager(self.target)

    @Lazy
    def presetTypesForAssignment(self):
        types = list(self.typeManager.listTypes(include=('assign',)))
        assigned = [r.context.conceptType for r in self.assignments]
        types = [t for t in types if t.typeProvider not in assigned]
        return [dict(title=t.title, token=t.tokenForSearch) for t in types]

    def conceptsForType(self, token):
        noSelection = dict(token='none', title=u'not selected')
        result = sorted(ConceptQuery(self).query(type=token), key=lambda x: x.title)
        predicateUid = self.defaultPredicateUid
        return ([noSelection] +
                [dict(title=o.title,
                      token='%s:%s' % (util.getUidForObject(o), predicateUid))
                 for o in result])


class EditObjectForm(ObjectForm):

    @Lazy
    def macro(self):
        return self.template.macros['edit']

    title = _(u'Edit Resource')
    form_action = 'edit_resource'
    dialog_name = 'edit'

    def __init__(self, context, request):
        super(EditObjectForm, self).__init__(context, request)
        #self.url = self.url # keep virtual target URL (???)
        self.target = self.virtualTargetObject

    @property
    def assignments(self):
        for c in self.target.getConceptRelations():
            r = ConceptRelationView(c, self.request)
            if r.isProtected: continue
            yield r


class EditConceptForm(EditObjectForm):

    isInnerHtml = True

    title = _(u'Edit Concept')
    form_action = 'edit_concept'

    @Lazy
    def dialog_name(self):
        return self.request.get('dialog', 'editConcept')

    @Lazy
    def typeInterface(self):
        return IType(self.target).typeInterface or IConceptSchema

    @property
    def assignments(self):
        for c in self.target.getParentRelations():
            r = ConceptRelationView(c, self.request)
            if not r.isProtected and r.context != self.target:
                yield r


class EditConceptPage(EditConceptForm):

    isInnerHtml = False

    def setupController(self):
        super(EditConceptPage, self).setupController()
        self.registerDojoFormAll()


class CreateObjectForm(ObjectForm):

    @property
    def macro(self): return self.template.macros['create']

    defaultTitle = u'Create Resource, Type = '
    form_action = 'create_resource'
    dialog_name = 'create'

    @Lazy
    def title(self):
        if self.request.form.get('fixed_type'):
            return _(u'Create %s') % self.typeConcept.title
        else:
            return _(self.defaultTitle)

    @Lazy
    def defaultTypeToken(self):
        return (self.controller.params.get('form.create.defaultTypeToken')
                or '.loops/concepts/textdocument')

    @Lazy
    def typeConcept(self):
        typeToken = self.request.get('form.type') or self.defaultTypeToken
        if typeToken:
            return self.loopsRoot.loopsTraverse(typeToken)

    @Lazy
    def adapted(self):
        ad = self.typeInterface(Resource())
        ad.storageName = 'unknown'  # hack for file objects: don't try to retrieve data
        return ad

    @Lazy
    def instance(self):
        instance = IInstance(self.adapted)
        instance.template = self.schema
        instance.view = self
        return instance

    @Lazy
    def typeInterface(self):
        tc = self.typeConcept
        if tc:
            return removeSecurityProxy(ITypeConcept(tc).typeInterface)
        else:
            return ITextDocument

    @property
    def assignments(self):
        target = self.virtualTargetObject
        if self.maybeAssignedAsParent(target):
            rv = ConceptRelationView(ResourceRelation(target, None), self.request)
            return (rv,)
        return ()

    def maybeAssignedAsParent(self, obj):
        if not IConcept.providedBy(obj):
            return False
        if obj.conceptType == self.loopsRoot.getConceptManager().getTypeConcept():
            return False
        if 'noassign' in IType(obj).qualifiers:
            return False
        adap = adapted(obj)
        if 'noassign' in getattr(adap, 'options', []):
            return False
        return True


class CreateObjectPopup(CreateObjectForm):

    isInnerHtml = False
    isPopup = True
    nextUrl = ''    # no redirect upon submit

    def update(self):
        show = super(ObjectForm, self).update()
        if not show:
            return False
        self.registerDojo()
        cm = self.controller.macros
        cm.register('css', identifier='popup.css', resourceName='popup.css',
                    media='all', position=4)
        jsCall = ('dojo.require("dojo.parser");'
                  'dojo.require("dijit.form.FilteringSelect");'
                  'dojo.require("dojox.data.QueryReadStore");')
        cm.register('js-execute', jsCall, jsCall=jsCall)
        return True

    def pageBody(self):
        return popupTemplate(self)


class CreateConceptForm(CreateObjectForm):

    defaultTitle = u'Create Concept, Type = '
    form_action = 'create_concept'

    @Lazy
    def dialog_name(self):
        return self.request.get('dialog', 'createConcept')

    @Lazy
    def adapted(self):
        c = Concept()
        ti = self.typeInterface
        if ti is None:
            return c
        ad = ti(c)
        return ad

    @Lazy
    def instance(self):
        instance = IInstance(self.adapted)
        instance.template = self.schema
        instance.view = self
        return instance

    @Lazy
    def typeInterface(self):
        if self.typeConcept:
            ti = ITypeConcept(self.typeConcept).typeInterface
            if ti is not None:
                return removeSecurityProxy(ti)
        return IConceptSchema

    @property
    def assignments(self):
        target = self.virtualTargetObject
        if self.maybeAssignedAsParent(target):
            rv = ConceptRelationView(ConceptRelation(target, None), self.request)
            return (rv,)
        return ()


class CreateConceptPage(CreateConceptForm):

    isInnerHtml = False

    def setupController(self):
        super(CreateConceptPage, self).setupController()
        self.registerDojoFormAll()

    @Lazy
    def nextUrl(self):
        return self.nodeView.getUrlForTarget(self.context)


class InnerForm(CreateObjectForm):

    @property
    def macro(self):
        return self.fieldRenderers['fields']


class InnerConceptForm(CreateConceptForm):

    @property
    def macro(self):
        return self.fieldRenderers['fields']


class InnerConceptEditForm(EditConceptForm):

    @property
    def macro(self):
        return self.fieldRenderers['fields']


# processing form input

class EditObject(FormController, I18NView):
    """ Note that ``self.context`` of this adapter may be different from
        ``self.object``, the object it acts upon, e.g. when this object
        is created during the update processing.
    """

    prefix = 'form.'
    conceptPrefix = 'assignments.'

    @Lazy
    def adapted(self):
        return adapted(self.object, self.languageInfoForUpdate)

    @Lazy
    def typeInterface(self):
        return IType(self.object).typeInterface or ITextDocument

    @Lazy
    def schema(self):
        schemaFactory = ISchemaFactory(self.adapted)
        return schemaFactory(self.typeInterface, manager=self,
                             request=self.request)

    @Lazy
    def fields(self):
        return self.schema.fields

    @Lazy
    def instance(self):
        instance = component.getAdapter(self.adapted, IInstance, name='editor')
        instance.template = self.schema
        instance.view = self.view
        return instance

    @Lazy
    def loopsRoot(self):
        return self.view.loopsRoot

    def update(self):
        # create new version if necessary
        target = self.view.virtualTargetObject
        obj = self.checkCreateVersion(target)
        if obj != target:
            # make sure new version is used by the view
            self.view.virtualTargetObject = obj
            viewAnnotations = self.request.annotations.setdefault('loops.view', {})
            viewAnnotations['target'] = obj
        self.object = obj
        formState = self.updateFields()
        self.view.formState = formState
        # TODO: error handling
        url = self.view.nextUrl
        if url is None:
            url = self.view.virtualTargetUrl + '?version=this'
        if url:
            self.request.response.redirect(url)
        return False

    def updateFields(self):
        obj = self.object
        form = self.request.form
        instance = self.instance
        formState = instance.applyTemplate(data=form, fieldHandlers=self.fieldHandlers)
        self.selected = []
        self.old = []
        stateKeys = []
        for k in form.keys():
            if k.startswith(self.prefix):
                fn = k[len(self.prefix):]
                value = form[k]
                if fn.startswith(self.conceptPrefix) and value:
                    self.collectConcepts(fn[len(self.conceptPrefix):], value)
            if k.startswith('state.'):
                stateKeys.append(k)
        self.collectAutoConcepts()
        if self.old or self.selected:
            self.assignConcepts(obj)
        for k in stateKeys:
            self.updateState(k)
        notify(ObjectModifiedEvent(obj))
        return formState

    def updateState(self, key):
        trans = self.request.form.get(key, '-')
        if trans == '-':
            return
        stdName = key[len('state.'):]
        stf = component.getAdapter(self.object, IStateful, name=stdName)
        stf.doTransition(trans)

    def handleFileUpload(self, context, value, fieldInstance, formState):
        """ Special handler for fileupload fields;
            value is a FileUpload instance.
        """
        filename = getattr(value, 'filename', '')
        if filename:    # ignore if no filename present - no file uploaded
            value = value.read()
            contentType = guess_content_type(filename, value[:100])
            if contentType:
                ct = contentType[0]
                self.request.form['form.contentType'] = ct
                context.contentType = ct
            setattr(context, fieldInstance.name, value)
            context.localFilename = filename

    @property
    def fieldHandlers(self):
        return dict(fileupload=self.handleFileUpload)

    def collectConcepts(self, fieldName, value):
        if self.old is None:
            self.old = []
        for v in value:
            if fieldName == 'old':
                self.old.append(v)
            elif fieldName == 'selected' and v not in self.selected:
                self.selected.append(v)

    def collectAutoConcepts(self):
        pass

    def assignConcepts(self, obj):
        for v in self.old:
            if v not in self.selected:
                c, p = v.split(':')
                concept = util.getObjectForUid(c)
                predicate = util.getObjectForUid(p)
                self.deassignConcept(obj, concept, [predicate])
        for v in self.selected:
            if v != 'none' and v not in self.old:
                c, p = v.split(':')
                concept = util.getObjectForUid(c)
                predicate = util.getObjectForUid(p)
                exists = self.getConceptRelations(obj, [p], concept)
                if not exists:
                    self.assignConcept(obj, concept, predicate)

    def getConceptRelations(self, obj, predicates, concept):
        return obj.getConceptRelations(predicates=predicates, concept=concept)

    def assignConcept(self, obj, concept, predicate):
        obj.assignConcept(concept, predicate)

    def deassignConcept(self, obj, concept, predicates):
        obj.deassignConcept(concept, predicates)

    def checkCreateVersion(self, obj):
        form = self.request.form
        if form.get('version.create'):
            versionable = IVersionable(obj)
            level = int(form.get('version.level', 1))
            version = versionable.createVersion(level)
            notify(ObjectCreatedEvent(version))
            return version
        return obj


class CreateObject(EditObject):

    factory = Resource
    defaultTypeToken = '.loops/concepts/textdocument'

    @Lazy
    def container(self):
        return self.loopsRoot.getResourceManager()

    def getNameFromData(self):
        data = self.request.form.get('data')
        if data and isinstance(data, FileUpload):
            name = getattr(data, 'filename', None)
            # strip path from IE uploads:
            if '\\' in name:
                name = name.rsplit('\\', 1)[-1]
        else:
            name = None
        return name

    def update(self):
        form = self.request.form
        container = self.container
        title = form.get('title')
        if not title:
            raise BadRequest('Title field is empty')
        obj = self.factory(title)
        name = self.getNameFromData()
        # TODO: validate fields
        name = INameChooser(container).chooseName(name, obj)
        container[name] = obj
        tc = form.get('form.type') or self.defaultTypeToken
        obj.setType(self.loopsRoot.loopsTraverse(tc))
        notify(ObjectCreatedEvent(obj))
        #notify(ObjectAddedEvent(obj))
        self.object = obj
        formState = self.updateFields() # TODO: suppress validation
        self.view.formState = formState
        # TODO: error handling
        url = self.view.nextUrl
        if url is None:
            self.request.response.redirect(self.view.request.URL)
        if url:
            self.request.response.redirect(url)
        return False


class EditConcept(EditObject):

    @Lazy
    def typeInterface(self):
        return IType(self.object).typeInterface or IConceptSchema

    def getConceptRelations(self, obj, predicates, concept):
        return obj.getParentRelations(predicates=predicates, parent=concept)

    def assignConcept(self, obj, concept, predicate):
        obj.assignParent(concept, predicate)

    def deassignConcept(self, obj, concept, predicates):
        obj.deassignParent(concept, predicates)

    def update(self):
        self.object = self.view.virtualTargetObject
        formState = self.updateFields()
        self.view.formState = formState
        # TODO: error handling
        if formState.severity > 0:
            return True
        self.request.response.redirect(self.view.virtualTargetUrl)
        return False


class CreateConcept(EditConcept, CreateObject):

    factory = Concept
    defaultTypeToken = '.loops/concepts/topic'

    @Lazy
    def container(self):
        return self.loopsRoot.getConceptManager()

    def getNameFromData(self):
        return None

    def update(self):
        return CreateObject.update(self)

