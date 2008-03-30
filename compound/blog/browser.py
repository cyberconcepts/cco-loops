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
View classes for glossary and glossary items.

$Id$
"""


import itertools
from zope import component
from zope.app.pagetemplate import ViewPageTemplateFile
from zope.cachedescriptors.property import Lazy

from cybertools.browser.action import actions
from cybertools.browser.member import IMemberInfoProvider
from loops.browser.action import DialogAction
from loops.browser.concept import ConceptView, ConceptRelationView
from loops.browser.form import CreateConceptForm, EditConceptForm
from loops.browser.form import CreateConcept, EditConcept
from loops.common import adapted
from loops.organize.party import getPersonForUser
from loops.security.common import checkPermission
from loops import util
from loops.util import _


view_macros = ViewPageTemplateFile('view_macros.pt')


actions.register('createBlogPost', 'portlet', DialogAction,
        title=_(u'Create Blog Post...'),
        description=_(u'Create a new blog post.'),
        viewName='create_blogpost.html',
        dialogName='createBlogPost',
        typeToken='.loops/concepts/blogpost',
        fixedType=True,
        innerForm='inner_concept_form.html',
        prerequisites=['registerDojoDateWidget'], # +'registerDojoTextWidget'?
)


def supplyCreator(self, data):
    creator = data.get('creator')
    data['creatorId'] = creator
    if creator:
        mip = component.getMultiAdapter((self.context, self.request),
                                        IMemberInfoProvider)
        mi = mip.getData(creator)
        data['creator'] = mi.title.value or creator
        obj = mi.get('object')
        if obj is not None:
            data['creatorUrl'] = self.controller.view.getUrlForTarget(obj.value)
    return data


class BlogRelationView(ConceptRelationView):

    @Lazy
    def data(self):
        data = super(BlogRelationView, self).data
        return supplyCreator(self, data)


class BlogView(ConceptView):

    childViewFactory = BlogRelationView

    @Lazy
    def macro(self):
        return view_macros.macros['blog']

    def getActions(self, category='object', page=None):
        blogOwnerId = self.blogOwnerId
        if blogOwnerId:
            principal = self.request.principal
            if principal and principal.id != blogOwnerId:
                return []
        return actions.get(category, ['createBlogPost'], view=self, page=page)

    @Lazy
    def blogOwnerId(self):
        pType = self.loopsRoot.getConceptManager()['person']
        persons = [p for p in self.context.getParents() if p.conceptType == pType]
        if len(persons) == 1:
            return adapted(persons[0]).userId
        return ''

    @Lazy
    def allChildren(self):
        return self.childrenByType()

    def blogPosts(self):
        posts = self.allChildren.get('blogpost', [])
        return reversed(sorted(posts, key=lambda x: x.adapted.date))

    def children(self, topLevelOnly=True, sort=True):
        rels = itertools.chain(*[self.allChildren[k]
                                 for k in self.allChildren.keys()
                                 if k != 'blogpost'])
        return sorted(rels, key=lambda r: (r.order, r.title.lower()))


class BlogPostView(ConceptView):

    @Lazy
    def macro(self):
        return view_macros.macros['blogpost']

    @Lazy
    def data(self):
        data = super(BlogPostView, self).data
        data = supplyCreator(self, data)
        if not checkPermission('loops.ViewRestricted', self.context):
            data['privateComment'] = u''
        return data

    def getActions(self, category='object', page=None):
        actions = []
        if category == 'portlet' and self.editable:
            actions.append(DialogAction(self, title=_(u'Edit Blog Post...'),
                  description=_(u'Modify blog post.'),
                  viewName='edit_blogpost.html',
                  dialogName='editBlogPost',
                  page=page))
            #self.registerDojoTextWidget()
            self.registerDojoDateWidget()
        return actions

    def render(self):
        return self.renderText(self.data['text'], self.adapted.textContentType)

    def resources(self):
        stdPred = self.loopsRoot.getConceptManager().getDefaultPredicate()
        rels = self.context.getResourceRelations([stdPred])
        for r in rels:
            yield self.childViewFactory(r, self.request, contextIsSecond=True)


class EditBlogPostForm(EditConceptForm):

    title = _(u'Edit Blog Post')
    form_action = 'edit_blogpost'


class CreateBlogPostForm(CreateConceptForm):

    title = _(u'Create Blog Post')
    form_action = 'create_blogpost'


class EditBlogPost(EditConcept):

    pass


class CreateBlogPost(CreateConcept):

    def collectAutoConcepts(self):
        #super(CreateBlogPost, self).collectConcepts(fieldName, value)
        person = getPersonForUser(self.container, self.request)
        if person is not None:
            concepts = self.loopsRoot.getConceptManager()
            blogType = concepts.get('blog')
            if blogType is not None:
                blogs = [c for c in person.getChildren()
                           if c.conceptType == blogType]
                if blogs:
                    blogUid = util.getUidForObject(blogs[0])
                    predUid = util.getUidForObject(concepts.getDefaultPredicate())
                    token = '%s:%s' % (blogUid, predUid)
                    if token not in self.selected:
                        self.selected.append(token)
