# Copyright 2021 Gentoo Authors
# Distributed under the terms of the GNU General Public License v2

import os
import re

from portage.versions import catpkgsplit

from twisted.internet import defer
from twisted.python import log

from buildbot.process.buildstep import BuildStep
from buildbot.process.results import SUCCESS
from buildbot.process.results import FAILURE
from buildbot.plugins import steps

def PersOutputOfEmerge(rc, stdout, stderr):
    emerge_output = {}
    emerge_output['rc'] = rc
    emerge_output['preserved_libs'] = False
    emerge_output['depclean'] = False
    package_dict = {}
    print(stderr)
    emerge_output['stderr'] = stderr
    # split the lines
    for line in stdout.split('\n'):
        # package list
        subdict = {}
        if line.startswith('[ebuild') or line.startswith('[binary'):
            # if binaries
            if line.startswith('[ebuild'):
                subdict['binary'] = False
            else:
                subdict['binary'] = True
            # action [ N ] stuff
            subdict['action'] = line[8:15].replace(' ', '')
            # cpv
            cpv_split = re.search('] (.+?) ', line).group(1).split(':')
            cpv = cpv_split[0]
            # repository
            # slot
            if cpv_split[1] == '':
                subdict['slot'] = None
                subdict['repository'] = cpv_split[2]
            else:
                subdict['slot'] = cpv_split[1]
                subdict['repository'] = cpv_split[3]
            # if action U version cpv
            if 'U' in subdict['action']:
                subdict['old_version'] = re.search(' \[(.+?)] ', line).group(1).split(':')
            else:
                subdict['old_version'] = None
            # Use list
            if 'USE=' in line:
                subdict['use'] = re.search('USE="(.+?)" ', line).group(1).split(' ')
            else:
                subdict['use'] = None
            # PYTHON_TARGETS list
            if 'PYTHON_TARGETS=' in line:
                subdict['python_targets'] = re.search('PYTHON_TARGETS="(.+?)" ', line).group(1).split(' ')
            else:
                subdict['python_targets'] = None
            # CPU_FLAGS_X86 list
            package_dict[cpv] = subdict
        if line.startswith('>>>'):
            #FIXME: Handling of >>> output
            pass
        if line.startswith('!!!'):
            #FIXME: Handling of !!! output
            if line.startswith('!!! existing preserved libs'):
                pass
        #FIXME: Handling of depclean output dict of packages that get removed or saved
    emerge_output['package'] = package_dict
    # split the lines
    #FIXME: Handling of stderr output
    for line in stderr.split('\n'):
        pass
    return {
        'emerge_output' : emerge_output
        }

def PersOutputOfPkgCheck(rc, stdout, stderr):
    pkgcheck_output = {}
    pkgcheck_output['rc'] = rc
    #FIXME: Handling of stdout output
    pkgcheck_xml_list = []
    # split the lines
    for line in stdout.split('\n'):
        #  pkgcheck output list
        if line.startswith('<checks'):
            pkgcheck_xml_list.append(line)
        if line.startswith('<result'):
            pkgcheck_xml_list.append(line)
        if line.startswith('</checks'):
            pkgcheck_xml_list.append(line)
    pkgcheck_output['pkgcheck_xml'] = pkgcheck_xml_list
    #FIXME: Handling of stderr output
    return {
        'pkgcheck_output' : pkgcheck_output
        }

class TriggerRunBuildRequest(BuildStep):
    
    name = 'TriggerRunBuildRequest'
    description = 'Running'
    descriptionDone = 'Ran'
    descriptionSuffix = None
    haltOnFailure = True
    flunkOnFailure = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @defer.inlineCallbacks
    def run(self):
        yield self.build.addStepsAfterCurrentStep([
                steps.Trigger(
                    schedulerNames=['run_build_request'],
                        waitForFinish=False,
                        updateSourceStamp=False,
                        set_properties={
                            'cpv' : self.getProperty("cpv"),
                            'version_data' : self.getProperty("version_data"),
                            'projectrepository_data' : self.getProperty('projectrepository_data'),
                            'use_data' : self.getProperty("use_data"),
                            'fullcheck' : self.getProperty("fullcheck"),
                        }
                )])
        return SUCCESS

class GetProjectRepositoryData(BuildStep):
    
    name = 'GetProjectRepositoryData'
    description = 'Running'
    descriptionDone = 'Ran'
    descriptionSuffix = None
    haltOnFailure = True
    flunkOnFailure = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @defer.inlineCallbacks
    def run(self):
        self.gentooci = self.master.namedServices['services'].namedServices['gentooci']
        self.projectrepositorys_data = yield self.gentooci.db.projects.getProjectRepositorysByUuid(self.getProperty("repository_data")['uuid'])
        if self.projectrepositorys_data is None:
            print('No Projects have this %s repository for testing' % self.getProperty("repository_data")['name'])
            return SUCCESS
        # for loop to get all the projects that have the repository
        for projectrepository_data in self.projectrepositorys_data:
            # get project data
            project_data = yield self.gentooci.db.projects.getProjectByUuid(projectrepository_data['project_uuid'])
            # check if auto, enabled and not in config.project['project']
            if project_data['auto'] is True and project_data['enabled'] is True and project_data['name'] != self.gentooci.config.project['project']:
                # set Property projectrepository_data so we can use it in the trigger
                self.setProperty('projectrepository_data', projectrepository_data, 'projectrepository_data')
                self.setProperty('use_data', None, 'use_data')
                # get name o project keyword
                project_keyword_data = yield self.gentooci.db.keywords.getKeywordById(project_data['keyword_id'])
                # if not * (all keywords)
                if project_keyword_data['name'] != '*' or project_data['status'] == 'all':
                    self.setProperty('fullcheck', False, 'fullcheck')
                    # get status of the keyword on cpv
                    version_keywords_data = self.getProperty("version_keyword_dict")[project_keyword_data['name']]
                    # if unstable trigger BuildRequest on cpv
                    if project_data['status'] == version_keywords_data['status']:
                        yield self.build.addStepsAfterCurrentStep([TriggerRunBuildRequest()])
        return SUCCESS

class SetupPropertys(BuildStep):
    
    name = 'SetupPropertys'
    description = 'Running'
    descriptionDone = 'Ran'
    descriptionSuffix = None
    haltOnFailure = True
    flunkOnFailure = True

    def __init__(self, **kwargs):
        # set this in config
        self.portage_repos_path = '/var/db/repos/'
        super().__init__(**kwargs)

    @defer.inlineCallbacks
    def run(self):
        self.gentooci = self.master.namedServices['services'].namedServices['gentooci']
        print('build this %s' % self.getProperty("cpv"))
        self.setProperty('portage_repos_path', self.portage_repos_path, 'portage_repos_path')
        projectrepository_data = self.getProperty('projectrepository_data')
        print(projectrepository_data)
        project_data = yield self.gentooci.db.projects.getProjectByUuid(projectrepository_data['project_uuid'])
        self.setProperty('project_data', project_data, 'project_data')
        self.setProperty('preserved_libs', False, 'preserved-libs')
        self.setProperty('depclean', False, 'depclean')
        self.setProperty('cpv_build', False, 'cpv_build')
        return SUCCESS

class UpdateRepos(BuildStep):

    name = 'UpdateRepos'
    description = 'Running'
    descriptionDone = 'Ran'
    descriptionSuffix = None
    haltOnFailure = True
    flunkOnFailure = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @defer.inlineCallbacks
    def run(self):
        self.gentooci = self.master.namedServices['services'].namedServices['gentooci']
        portage_repos_path = self.getProperty('portage_repos_path')
        project_data = self.getProperty('project_data')
        # update/add all repos that in project_repository for the project
        projects_repositorys_data = yield self.gentooci.db.projects.getRepositorysByProjectUuid(project_data['uuid'])
        for project_repository_data in projects_repositorys_data:
            repository_data = yield self.gentooci.db.repositorys.getRepositoryByUuid(project_repository_data['repository_uuid'])
            repository_path = yield os.path.join(portage_repos_path, repository_data['name'])
            yield self.build.addStepsAfterCurrentStep([
            steps.Git(repourl=repository_data['mirror_url'],
                            mode='incremental',
                            submodules=True,
                            workdir=os.path.join(repository_path, ''))
            ])
        return SUCCESS

class RunEmerge(BuildStep):

    name = 'RunEmerge'
    description = 'Running'
    descriptionDone = 'Ran'
    descriptionSuffix = None
    haltOnFailure = True
    flunkOnFailure = True

    def __init__(self, step=None,**kwargs):
        self.step = step
        super().__init__(**kwargs)

    @defer.inlineCallbacks
    def run(self):
        self.gentooci = self.master.namedServices['services'].namedServices['gentooci']
        project_data = self.getProperty('project_data')
        projects_emerge_options = yield self.gentooci.db.projects.getProjectEmergeOptionsByUuid(project_data['uuid'])
        shell_commad_list = [
                    'emerge',
                    '-v'
                    ]
        aftersteps_list = []
        if self.step == 'pre-update':
            shell_commad_list.append('-uDN')
            shell_commad_list.append('--changed-deps')
            shell_commad_list.append('--changed-use')
            shell_commad_list.append('--pretend')
            shell_commad_list.append('@world')
            # don't build bin for virtual and acct-*
            shell_commad_list.append('--buildpkg-exclude')
            shell_commad_list.append('virtual')
            shell_commad_list.append('--buildpkg-exclude')
            shell_commad_list.append('acct-*')
            aftersteps_list.append(
                steps.SetPropertyFromCommandNewStyle(
                        command=shell_commad_list,
                        strip=True,
                        extract_fn=PersOutputOfEmerge,
                        workdir='/'
                ))
            aftersteps_list.append(CheckEmergeLogs('pre-update'))

        if self.step == 'update':
            shell_commad_list.append('-uDNq')
            shell_commad_list.append('--changed-deps')
            shell_commad_list.append('--changed-use')
            shell_commad_list.append('@world')
            # don't build bin for virtual and acct-*
            shell_commad_list.append('--buildpkg-exclude')
            shell_commad_list.append('virtual')
            shell_commad_list.append('--buildpkg-exclude')
            shell_commad_list.append('acct-*')
            aftersteps_list.append(
                steps.SetPropertyFromCommandNewStyle(
                        command=shell_commad_list,
                        strip=True,
                        extract_fn=PersOutputOfEmerge,
                        workdir='/',
                        timeout=None
                ))
            aftersteps_list.append(CheckEmergeLogs('update'))
            if projects_emerge_options['preserved_libs']:
                self.setProperty('preserved_libs', True, 'preserved-libs')

        if self.step == 'preserved-libs' and self.getProperty('preserved_libs'):
            shell_commad_list.append('-q')
            shell_commad_list.append('@preserved-rebuild')
            aftersteps_list.append(
                steps.SetPropertyFromCommandNewStyle(
                        command=shell_commad_list,
                        strip=True,
                        extract_fn=PersOutputOfEmerge,
                        workdir='/',
                        timeout=None
                ))
            aftersteps_list.append(CheckEmergeLogs('preserved-libs'))
            self.setProperty('preserved_libs', False, 'preserved-libs')

        if self.step == 'pre-depclean' and projects_emerge_options['depclean']:
            shell_commad_list.append('--pretend')
            shell_commad_list.append('--depclean')
            aftersteps_list.append(
                steps.SetPropertyFromCommandNewStyle(
                        command=shell_commad_list,
                        strip=True,
                        extract_fn=PersOutputOfEmerge,
                        workdir='/'
                ))
            aftersteps_list.append(CheckEmergeLogs('depclean'))

        if self.step == 'depclean' and self.getProperty('depclean'):
            shell_commad_list.append('-q')
            shell_commad_list.append('--depclean')
            aftersteps_list.append(
                steps.SetPropertyFromCommandNewStyle(
                        command=shell_commad_list,
                        strip=True,
                        extract_fn=PersOutputOfEmerge,
                        workdir='/'
                ))
            aftersteps_list.append(CheckEmergeLogs('depclean'))

        if self.step == 'match':
            cpv = self.getProperty("cpv")
            c = yield catpkgsplit(cpv)[0]
            p = yield catpkgsplit(cpv)[1]
            shell_commad_list.append('-pO')
            # don't use bin for match
            shell_commad_list.append('--usepkg=n')
            shell_commad_list.append(c + '/' + p)
            aftersteps_list.append(
                steps.SetPropertyFromCommandNewStyle(
                        command=shell_commad_list,
                        strip=True,
                        extract_fn=PersOutputOfEmerge,
                        workdir='/',
                        timeout=None
                ))
            aftersteps_list.append(CheckEmergeLogs('match'))

        if self.step == 'pre-build':
            cpv = self.getProperty("cpv")
            c = yield catpkgsplit(cpv)[0]
            p = yield catpkgsplit(cpv)[1]
            shell_commad_list.append('-p')
            shell_commad_list.append('=' + self.getProperty('cpv'))
            # we don't use the bin for the requsted cpv
            shell_commad_list.append('--usepkg-exclude')
            shell_commad_list.append(c + '/' + p)
            # don't build bin for virtual and acct-*
            shell_commad_list.append('--buildpkg-exclude')
            shell_commad_list.append('virtual')
            shell_commad_list.append('--buildpkg-exclude')
            shell_commad_list.append('acct-*')
            aftersteps_list.append(
                steps.SetPropertyFromCommandNewStyle(
                        command=shell_commad_list,
                        strip=True,
                        extract_fn=PersOutputOfEmerge,
                        workdir='/',
                        timeout=None
                ))
            aftersteps_list.append(CheckEmergeLogs('pre-build'))

        if self.step == 'build':
            cpv = self.getProperty("cpv")
            c = yield catpkgsplit(cpv)[0]
            p = yield catpkgsplit(cpv)[1]
            shell_commad_list.append('-q')
            if projects_emerge_options['oneshot']:
                shell_commad_list.append('-1')
            shell_commad_list.append('=' + self.getProperty('cpv'))
            # we don't use the bin for the requsted cpv
            shell_commad_list.append('--usepkg-exclude')
            shell_commad_list.append(c + '/' + p)
            # don't build bin for virtual and acct-*
            shell_commad_list.append('--buildpkg-exclude')
            shell_commad_list.append('virtual')
            shell_commad_list.append('--buildpkg-exclude')
            shell_commad_list.append('acct-*')
            aftersteps_list.append(
                steps.SetPropertyFromCommandNewStyle(
                        command=shell_commad_list,
                        strip=True,
                        extract_fn=PersOutputOfEmerge,
                        workdir='/',
                        timeout=None
                ))
            aftersteps_list.append(CheckEmergeLogs('build'))
            if projects_emerge_options['preserved_libs']:
                self.setProperty('preserved_libs', True, 'preserved-libs')

        if not self.step is None and aftersteps_list != []:
            yield self.build.addStepsAfterCurrentStep(aftersteps_list)
        return SUCCESS

class CheckEmergeLogs(BuildStep):

    name = 'CheckLogs'
    description = 'Running'
    descriptionDone = 'Ran'
    descriptionSuffix = None
    haltOnFailure = True
    flunkOnFailure = True

    def __init__(self, step=None,**kwargs):
        self.step = step
        super().__init__(**kwargs)

    @defer.inlineCallbacks
    def run(self):
        self.gentooci = self.master.namedServices['services'].namedServices['gentooci']
        project_data = self.getProperty('project_data')
        projects_emerge_options = yield self.gentooci.db.projects.getProjectEmergeOptionsByUuid(project_data['uuid'])
        emerge_output = self.getProperty('emerge_output')
        shell_commad_list = [
                    'emerge',
                    '-v'
                    ]
        aftersteps_list = []

        #FIXME: Prosees the logs and do stuff
        # preserved-libs
        if emerge_output['preserved_libs'] and projects_emerge_options['preserved_libs']:
            self.setProperty('preserved_libs', True, 'preserved-libs')
        # depclean
        # FIXME: check if don't remove needed stuff.
        if emerge_output['depclean'] and projects_emerge_options['depclean']:
            self.setProperty('depclean', True, 'depclean')

        # FIXME: check if cpv match
        if self.step == 'match'and self.getProperty('projectrepository_data')['build']:
            if self.getProperty('cpv') in emerge_output['package']:
                self.setProperty('cpv_build', True, 'cpv_build')
            print(self.getProperty('cpv_build'))

        #FIXME:
        # update package.* if needed and rerun pre-build max X times
        if self.step == 'pre-build':
            print(emerge_output)

        if not self.step is None and aftersteps_list != []:
            yield self.build.addStepsAfterCurrentStep(aftersteps_list)
        return SUCCESS

class RunPkgCheck(BuildStep):

    name = 'RunPkgCheck'
    description = 'Running'
    descriptionDone = 'Ran'
    descriptionSuffix = None
    haltOnFailure = True
    flunkOnFailure = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @defer.inlineCallbacks
    def run(self):
        projectrepository_data = self.getProperty('projectrepository_data')
        if not projectrepository_data['pkgcheck']:
            return SUCCESS
        self.gentooci = self.master.namedServices['services'].namedServices['gentooci']
        project_data = self.getProperty('project_data')
        portage_repos_path = self.getProperty('portage_repos_path')
        repository_data = yield self.gentooci.db.repositorys.getRepositoryByUuid(projectrepository_data['repository_uuid'])
        repository_path = yield os.path.join(portage_repos_path, repository_data['name'])
        cpv = self.getProperty("cpv")
        c = yield catpkgsplit(cpv)[0]
        p = yield catpkgsplit(cpv)[1]
        shell_commad_list = [
                    'pkgcheck',
                    'scan',
                    '-v'
                    ]
        shell_commad_list.append('-R')
        shell_commad_list.append('XmlReporter')
        aftersteps_list = []
        if projectrepository_data['pkgcheck'] == 'full':
            pkgcheck_workdir = yield os.path.join(repository_path, '')
        else:
            pkgcheck_workdir = yield os.path.join(repository_path, c, p, '')
        aftersteps_list.append(
            steps.SetPropertyFromCommandNewStyle(
                        command=shell_commad_list,
                        strip=True,
                        extract_fn=PersOutputOfPkgCheck,
                        workdir=pkgcheck_workdir
            ))
        aftersteps_list.append(CheckPkgCheckLogs())
        yield self.build.addStepsAfterCurrentStep(aftersteps_list)
        return SUCCESS

class CheckPkgCheckLogs(BuildStep):

    name = 'CheckPkgCheckLogs'
    description = 'Running'
    descriptionDone = 'Ran'
    descriptionSuffix = None
    haltOnFailure = True
    flunkOnFailure = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    #@defer.inlineCallbacks
    def run(self):
        self.gentooci = self.master.namedServices['services'].namedServices['gentooci']
        project_data = self.getProperty('project_data')
        pkgcheck_output = self.getProperty('pkgcheck_output')
        print(pkgcheck_output)
        #FIXME:
        # Perse the logs
        # tripp irc request with pkgcheck info
        return SUCCESS

class RunBuild(BuildStep):

    name = 'RunBuild'
    description = 'Running'
    descriptionDone = 'Ran'
    descriptionSuffix = None
    haltOnFailure = True
    flunkOnFailure = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @defer.inlineCallbacks
    def run(self):
        if not self.getProperty('cpv_build'):
            return SUCCESS
        aftersteps_list = []
        aftersteps_list.append(RunEmerge(step='pre-build'))
        aftersteps_list.append(RunEmerge(step='build'))
        self.setProperty('depclean', False, 'depclean')
        self.setProperty('preserved_libs', False, 'preserved-libs')
        yield self.build.addStepsAfterCurrentStep(aftersteps_list)
        return SUCCESS
