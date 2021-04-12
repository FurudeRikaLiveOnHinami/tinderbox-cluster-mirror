# Copyright 2021 Gentoo Authors
# Distributed under the terms of the GNU General Public License v2

import os
import pygit2

from twisted.internet import defer

from buildbot.process.buildstep import BuildStep
from buildbot.process.results import SUCCESS
from buildbot.process.results import FAILURE
from buildbot.process.results import SKIPPED
from buildbot.plugins import steps
from buildbot.config import error as config_error

class CheckPathRepositoryLocal(BuildStep):

    name = 'CheckPathRepositoryLocal'
    description = 'Running'
    descriptionDone = 'Ran'
    descriptionSuffix = None
    haltOnFailure = True
    flunkOnFailure = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def run(self):
        self.gentooci = self.master.namedServices['services'].namedServices['gentooci']
        # self.repository_basedir = self.gentooci.config.project['mirror_repository_basedir']
        repository_basedir = '/home/repos2/'
        self.setProperty("repository_basedir", repository_basedir, 'repository_basedir')
        if os.path.isdir(repository_basedir):
            return SUCCESS
        return FAILURE

class CheckRepository(BuildStep):

    name = 'CheckRepository'
    description = 'Running'
    descriptionDone = 'Ran'
    haltOnFailure = True
    flunkOnFailure = True

    def __init__(self, step=None, **kwargs):
        self.step = step
        super().__init__(**kwargs)

    # Origin: https://github.com/MichaelBoselowitz/pygit2-examples/blob/master/examples.py#L54
    # Modifyed by Gentoo Authors.
    def gitPull(self, repo, remote_name='origin', branch='master'):
        for remote in repo.remotes:
            if remote.name == remote_name:
                remote.fetch()
                remote_master_id = repo.lookup_reference('refs/remotes/origin/%s' % (branch)).target
                print(remote_master_id)
                merge_result, _ = repo.merge_analysis(remote_master_id)
                print(merge_result)
                # Up to date, do nothing
                if merge_result & pygit2.GIT_MERGE_ANALYSIS_UP_TO_DATE:
                    print('UP_TO_DATE')
                    return None
                # We can just fastforward
                elif merge_result & pygit2.GIT_MERGE_ANALYSIS_FASTFORWARD:
                    print('FASTFORWARD')
                    repo.checkout_tree(repo.get(remote_master_id))
                    try:
                        master_ref = repo.lookup_reference('refs/heads/%s' % (branch))
                        master_ref.set_target(remote_master_id)
                    except KeyError:
                        repo.create_branch(branch, repo.get(remote_master_id))
                    repo.head.set_target(remote_master_id)
                    return True
                elif merge_result & pygit2.GIT_MERGE_ANALYSIS_NORMAL:
                    print('NORMAL')
                    repo.merge(remote_master_id)
                    if repo.index.conflicts is not None:
                        for conflict in repo.index.conflicts:
                            print('Conflicts found in:', conflict[0].path)
                        raise AssertionError('Conflicts, ahhhhh!!')

                    user = repo.default_signature
                    tree = repo.index.write_tree()
                    commit = repo.create_commit('HEAD',
                                            user,
                                            user,
                                            'Merge!',
                                            tree,
                                            [repo.head.target, remote_master_id])
                    # We need to do this or git CLI will think we are still merging.
                    repo.state_cleanup()
                    return True
                else:
                    raise AssertionError('Unknown merge analysis result')
        return True

    @defer.inlineCallbacks
    def setchmod(self, path):
        for root, dirs, files in os.walk(path):
            for d in dirs:
                yield os.chmod(os.path.join(root, d), 0o0755)
            for f in files:
                yield os.chmod(os.path.join(root, f), 0o0644)

    @defer.inlineCallbacks
    def checkRepos(self, repository_data):
        repository_path = yield os.path.join(self.getProperty("repository_basedir"), repository_data['name'])
        repo_path = yield pygit2.discover_repository(repository_path)
        print(repo_path)
        if repo_path is None:
            yield pygit2.clone_repository(repository_data['mirror_url'], repository_path)
            success = True
        else:
            repo = yield pygit2.Repository(repo_path)
            commit = repo.get(repo.head.target)
            success = yield self.gitPull(repo)
            print(commit.hex)
            print(commit.commit_time)
        # chmod needed for ebuilds metadata portage.GetAuxMetadata step
        yield self.setchmod(repository_path)
        return success

    @defer.inlineCallbacks
    def run(self):
        #FIXME: # move som of it to buildfactory update_repo_check
        if self.step == 'profile':
            if self.getProperty("profile_repository_uuid") == self.getProperty("repository_uuid"):
                return SKIPPED
            repository_uuid = self.getProperty("profile_repository_uuid")
        else:
            repository_uuid = self.getProperty("repository_uuid")
        #---
        self.gentooci = self.master.namedServices['services'].namedServices['gentooci']
        repository_data = yield self.gentooci.db.repositorys.getRepositoryByUuid(repository_uuid)
        self.descriptionSuffix = repository_data['name']
        if repository_data['type'] == 'gitpuller':
            Poller_data = yield self.gentooci.db.repositorys.getGitPollerByUuid(repository_uuid)
        print(Poller_data['updated_at'])
        print(self.getProperty("commit_time"))
        if Poller_data['updated_at'] > self.getProperty("commit_time"):
            return SKIPPED
        success = yield self.checkRepos(repository_data)
        if success is None:
            return SKIPPED
        if not success:
            return FAILURE
        if repository_data['type'] == 'gitpuller':
            yield self.gentooci.db.repositorys.updateGitPollerTime(repository_uuid)
        return SUCCESS