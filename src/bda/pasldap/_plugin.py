# Copyright (c) 2006-2009 BlueDynamics Alliance, Austria http://bluedynamics.com
# GNU General Public License (GPL)


#import socket, os
#import types
#from sets import Set

#from Acquisition import Implicit, aq_parent, aq_base, aq_inner
#from AccessControl import getSecurityManager
#from OFS.Cache import Cacheable
#from Products.PlonePAS.plugins.group import PloneGroup
#from Products.PluggableAuthService.permissions import ManageGroups
#from Products.PluggableAuthService.UserPropertySheet import UserPropertySheet


import logging
logger = logging.getLogger('bda.plone.ldap')

import Acquisition
import sys
from zope.component import getUtility
from zope.interface import Interface, implements
from Products.CMFPlone.interfaces import IPloneSiteRoot
from Products.PluggableAuthService.plugins.BasePlugin import BasePlugin
from Products.PluggableAuthService.interfaces import plugins as pas_interfaces
from Products.PlonePAS import interfaces as plonepas_interfaces

from bda.ldap.users import LDAPUsers
#from bda.ldap.groups import LDAPGroups


WHAT_TO_DEBUG = set([
        'authentication',
        'userenumeration',
        ])


class debug:
    """ Decorator which helps to control what aspects of a program to debug
    on per-function basis. Aspects are provided as list of arguments.
    It DOESN'T slowdown functions which aren't supposed to be debugged.
    """
    def __init__(self, aspects=None):
        self.aspects = set(aspects)

    def __call__(self, func): 
        if self.aspects & WHAT_TO_DEBUG:
            def newfunc(*args, **kws):
                logger.debug('%s: args=%s, kws=%s', func.func_name, args, kws)
                result = func(*args, **kws)
                logger.debug('%s: --> %s', func.func_name, result)
                return result
            newfunc.__doc__ = func.__doc__
            return newfunc
        else:
            return func


class UsersReadOnly(BasePlugin):
    """Glue layer for making bda.ldap available to PAS, readonly users. 
    """
    # Tell PAS not to swallow our exceptions
    _dont_swallow_my_exceptions = True
    meta_type = 'ReadOnlyLDAPUsers'
    implements(
            pas_interfaces.IAuthenticationPlugin,
            pas_interfaces.IUserEnumerationPlugin,
            pas_interfaces.IPropertiesPlugin,
### probably not needed here:
#            pas_interfaces.ICredentialsResetPlugin,
#            pas_interfaces.IGroupEnumerationPlugin,
#            pas_interfaces.IGroupsPlugin,
#            pas_interfaces.IRolesPlugin,
#            pas_interfaces.IRoleEnumerationPlugin,
#            pas_interfaces.IUpdatePlugin,
#            pas_interfaces.IValidationPlugin,
#            plonepas_interfaces.group.IGroupIntrospection,
#            plonepas_interfaces.group.IGroupManagement,
#            plonepas_interfaces.plugins.IMutablePropertiesPlugin,
#            plonepas_interfaces.plugins.IUserIntrospection,
#            plonepas_interfaces.plugins.IUserManagement,
            )

    def __init__(self, id, title=None):
        self.id = id
        self.title = title
        self._portal = getUtility(IPloneSiteRoot)

    @property
    def users(self):
        try:
            return self._v_users
        except AttributeError:
            self._init_users()
            return self._v_users

    def _init_users(self):
        # get config
        #props = ILDAPProps(self._portal)
        #gcfg = ILDAPGroupsConfig(self._portal)
        #ucfg = ILDAPUsersConfig(self._portal)
        from bda.ldap.testing import props, ucfg
        ucfg.props.port = 22345
        # create users / groups
        self._v_users = LDAPUsers(ucfg)
        #self._v_groups = LDAPGroups(gcfg)

    ###
    # pas_interfaces.IAuthenticationPlugin
    #
    #  Map credentials to a user ID.
    #
    @debug(['authentication'])
    def authenticateCredentials(self, credentials):
        """ credentials -> (userid, login)

        o 'credentials' will be a mapping, as returned by IExtractionPlugin.

        o Return a  tuple consisting of user ID (which may be different 
          from the login name) and login

        o If the credentials cannot be authenticated, return None.
        """
        if credentials['login'] in ('fakelogin1', 'fakelogin2') and \
                credentials['password'] == 'fakepwd':
            return (
                    credentials['login'].replace('login', 'uid'),
                    credentials['login'],
                    )

    ###
    # pas_interfaces.IUserEnumerationPlugin
    #
    #   Allow querying users by ID, and searching for users.
    #    o XXX:  can these be done by a single plugin?
    #
    @debug(['userenumeration'])
    def enumerateUsers(self, id=None, login=None, exact_match=False,
            sort_by=None, max_results=None, **kws):
        """ -> ( user_info_1, ... user_info_N )

        o Return mappings for users matching the given criteria.

        o 'id' or 'login', in combination with 'exact_match' true, will
          return at most one mapping per supplied ID ('id' and 'login'
          may be sequences).

        o If 'exact_match' is False, then 'id' and / or login may be
          treated by the plugin as "contains" searches (more complicated
          searches may be supported by some plugins using other keyword
          arguments).

        o If 'sort_by' is passed, the results will be sorted accordingly.
          known valid values are 'id' and 'login' (some plugins may support
          others).

        o If 'max_results' is specified, it must be a positive integer,
          limiting the number of returned mappings.  If unspecified, the
          plugin should return mappings for all users satisfying the criteria.

        o Minimal keys in the returned mappings:
        
          'id' -- (required) the user ID, which may be different than
                  the login name

          'login' -- (required) the login name

          'pluginid' -- (required) the plugin ID (as returned by getId())

          'editurl' -- (optional) the URL to a page for updating the
                       mapping's user

        o Plugin *must* ignore unknown criteria.

        o Plugin may raise ValueError for invalid criteria.

        o Insufficiently-specified criteria may have catastrophic
          scaling issues for some implementations.
        """
        # no support for id and login being lists
        fakeusers = (
                dict(id='fakeuid1', login='fakelogin1', pluginid=self.getId()),
                dict(id='fakeuid2', login='fakelogin2', pluginid=self.getId()),
                )
        if exact_match:
            if login == 'fakelogin1' or id == 'fakeuid1':
                return (fakeusers[0],)
            elif login == 'fakelogin2' or id == 'fakeuid2':
                return (fakeusers[1],)
        else:
            return fakeusers

    ###
    # pas_interfaces.IPropertiesPlugin
    #
    #    Return a property set for a user.
    #
    def getPropertiesForUser(self, user, request=None):
        """ user -> {}

        o User will implement IPropertiedUser.

        o Plugin should return a dictionary or an object providing
          IPropertySheet.

        o Plugin may scribble on the user, if needed (but must still
          return a mapping, even if empty).

        o May assign properties based on values in the REQUEST object, if
          present
        """
        fakeprops = dict(
                fakeuid1 = {'email': 'fake1@email.com', 'fullname': 'Fake User1'},
                fakeuid2 = {'email': 'fake2@email.com', 'fullname': 'Fake User2'},
                )
        try:
            return fakeprops[user.getId()]
        except KeyError:
            return




### attic below here



# XXX: Is this really neeeded
class ILDAPPlugin(Interface):
    """Marker Interface
    """ 

# class LDAPPlugin(Users):
#    """
#    """
class LDAPPlugin(BasePlugin):
    """Glue layer for making bda.ldap available to PAS
    """
    # Tell PAS not to swallow our exceptions
    _dont_swallow_my_exceptions = True
    meta_type = 'LDAPPlugin'
    implements(ILDAPPlugin,
            pas_interfaces.IAuthenticationPlugin,
#            pas_interfaces.ICredentialsResetPlugin,
#            pas_interfaces.IGroupEnumerationPlugin,
#            pas_interfaces.IGroupsPlugin,
#            pas_interfaces.IRolesPlugin,
#            pas_interfaces.IRoleEnumerationPlugin,
#            pas_interfaces.IUpdatePlugin,
            pas_interfaces.IUserEnumerationPlugin,
#            pas_interfaces.IValidationPlugin,
#            plonepas_interfaces.group.IGroupIntrospection,
#            plonepas_interfaces.group.IGroupManagement,
            pas_interfaces.IPropertiesPlugin,
#            plonepas_interfaces.plugins.IMutablePropertiesPlugin,
#            plonepas_interfaces.plugins.IUserIntrospection,
#            plonepas_interfaces.plugins.IUserManagement,
            )

    def __init__(self, id, title=None):
        self.id = id
        self.title = title
        self._portal = getUtility(IPloneSiteRoot)

    @property
    def users(self):
        try:
            return self._v_users
        except AttributeError:
            self._init_ldap()
            return self._v_users

    @property
    def groups(self):
        try:
            return self._v_groups
        except AttributeError:
            self._init_ldap()
            return self._v_groups

    def _init_ldap(self):
        # get config
        #props = ILDAPProps(self._portal)
        #gcfg = ILDAPGroupsConfig(self._portal)
        #ucfg = ILDAPUsersConfig(self._portal)
        from bda.ldap.testing import props, ucfg
        ucfg.props.port = 22345
        # create users / groups
        self._v_users = LDAPUsers(ucfg)
        #self._v_groups = LDAPGroups(gcfg)

    ###
    # pas_interfaces.IAuthenticationPlugin
    #
    #  Map credentials to a user ID.

    @debug(['authentication'])
    def authenticateCredentials(self, credentials):
        """ credentials -> (userid, login)

        o 'credentials' will be a mapping, as returned by IExtractionPlugin.

        o Return a  tuple consisting of user ID (which may be different 
          from the login name) and login

        o If the credentials cannot be authenticated, return None.
        """
        uid = self.users.authenticate(
                credentials['login'],
                credentials['password'],
                )
        if uid:
            return (uid, credentials['login'])


    ###
    # pas_interfaces.IUserEnumerationPlugin
    #
    #   Allow querying users by ID, and searching for users.
    #    o XXX:  can these be done by a single plugin?

    @debug(['userenumeration'])
    def enumerateUsers(self, id=None, login=None, exact_match=False,
            sort_by=None, max_results=None, **kws):
        """ -> ( user_info_1, ... user_info_N )

        o Return mappings for users matching the given criteria.

        o 'id' or 'login', in combination with 'exact_match' true, will
          return at most one mapping per supplied ID ('id' and 'login'
          may be sequences).

        o If 'exact_match' is False, then 'id' and / or login may be
          treated by the plugin as "contains" searches (more complicated
          searches may be supported by some plugins using other keyword
          arguments).

        o If 'sort_by' is passed, the results will be sorted accordingly.
          known valid values are 'id' and 'login' (some plugins may support
          others).

        o If 'max_results' is specified, it must be a positive integer,
          limiting the number of returned mappings.  If unspecified, the
          plugin should return mappings for all users satisfying the criteria.

        o Minimal keys in the returned mappings:
        
          'id' -- (required) the user ID, which may be different than
                  the login name

          'login' -- (required) the login name

          'pluginid' -- (required) the plugin ID (as returned by getId())

          'editurl' -- (optional) the URL to a page for updating the
                       mapping's user

        o Plugin *must* ignore unknown criteria.

        o Plugin may raise ValueError for invalid criteria.

        o Insufficiently-specified criteria may have catastrophic
          scaling issues for some implementations.
        """
        # TODO: max_results in bda.ldap
        # TODO: sort_by in bda.ldap
        if id:
            kws['id'] = id
        if login:
            kws['login'] = login
        matches = self.users.search(
                criteria=kws,
                attrlist=('id', 'login'),
                exact_match=exact_match
                )



#### Below here unused so far




    ###
    # pas_interfaces.IGroupsPlugin
    def getGroupsForPrincipal(self, principal, request=None):

        """ principal -> ( group_1, ... group_N )

        o Return a sequence of group names to which the principal 
          (either a user or another group) belongs.

        o May assign groups based on values in the REQUEST object, if present
        """

    ###
    # pas_interfaces.IPropertiesPlugin
    # plonepas_interfaces.plugins.IMutablePropertiesPlugin
    #
    #    Return a property set for a user. Property set can either an
    #    object conforming to the IMutable property sheet interface or a
    #    dictionary (in which case the properties are not persistently
    #    mutable).

    # pas_interfaces.IPropertiesPlugin,
    def getPropertiesForUser(self, user, request=None):
        """
        User -> IMutablePropertySheet || {}

        o User will implement IPropertiedUser.

        o Plugin may scribble on the user, if needed (but must still
          return a mapping, even if empty).

        o May assign properties based on values in the REQUEST object, if
          present
        """

    # plonepas_interfaces.plugins.IMutablePropertiesPlugin
    def setPropertiesForUser(self, user, propertysheet):
        """
        Set modified properties on the user persistently.

        Raise a ValueError if the property or property value is invalid
        """

    # plonepas_interfaces.plugins.IMutablePropertiesPlugin
    def deleteUser(self, user_id):
        """
        Remove properties stored for a user
        """


    ####
    # pas_interfaces.IUserAdderPlugin
    # plonepas_interfaces.plugins.IUserManagement

    def doAddUser(self, login, password):
        """ Add a user record to a User Manager, with the given login
            and password

        o Return a Boolean indicating whether a user was added or not
        """
        if login == 'test_user_1_':
            logger.warn("Not creating Zope's testuser '%s' in ldap.")
            return False
