# Copyright 2021 Gentoo Authors
# Distributed under the terms of the GNU General Public License v2

from buildbot.plugins import steps as buildbot_steps
from buildbot.plugins import util
from twisted.internet import defer

from buildbot_gentoo_ci.steps import update_db
from buildbot_gentoo_ci.steps import category
from buildbot_gentoo_ci.steps import package
from buildbot_gentoo_ci.steps import version
from buildbot_gentoo_ci.steps import builders
from buildbot_gentoo_ci.steps import portage
from buildbot_gentoo_ci.steps import logs
from buildbot_gentoo_ci.steps import repos
from buildbot_gentoo_ci.steps import nodes

def update_db_check():
    f = util.BuildFactory()
    # FIXME: 1
    # Get base project data from db
    #   return profile_repository, project
    f.addStep(update_db.GetDataGentooCiProject())
    # update the repos
    f.addStep(update_db.TriggerUpdateRepositorys())
    # Make a for loop and trigger new builders with cpv from git_changes
    #   return cpv, repository, project_data
    f.addStep(update_db.TriggerCheckForCPV())
    return f

def update_repo_check():
    f = util.BuildFactory()
    # FIXME: 6
    # Check if needed path is there
    f.addStep(repos.CheckPathRepositoryLocal())
    # update the repos
    # FIXME:
    # use doStepIf so we don't need to do step=profile
    f.addStep(repos.CheckRepository(step='profile'))
    f.addStep(repos.CheckRepository())
    return f

def update_db_cp():
    f = util.BuildFactory()
    # FIXME: 2
    # if categorys in db
    #   return category_data
    #   add check category path step at end
    # else
    #   add category to db step
    #   return category_data
    f.addStep(category.CheckC())
    # if package in db
    #   return package_data
    #   add check package path step at end
    # else
    #   add package to db step
    #   return package_data
    f.addStep(package.CheckP())
    # Trigger new builders with v from cpv
    #   return package_data, cpv, repository_data, project_data
    f.addStep(package.TriggerCheckForV())
    return f

def update_db_v():
    f = util.BuildFactory()
    # FIXME: 3
    # if version in db
    #   return version_data
    f.addStep(version.GetVData())
    #   check path and hash
    f.addStep(version.CheckPathHash())
    #   if not path
    #       if not hash
    #           add deleted stage att end
    #           add version to db stage
    #           add version metadata to db
    #           add version to build check
    #   else
    #       add deleted stage att end
    #       add version to build check stage att end
    # else
    #   add version to db
    #   add version metadata to db
    #   add version to build check
    f.addStep(version.CheckV())
    return f

def build_request_check():
    f = util.BuildFactory()
    # FIXME: 4
    # get project_data
    # check what tests to do
    # triggger build request
    f.addStep(builders.GetProjectRepositoryData())
    return f

#@defer.inlineCallbacks
def run_build_request():
    f = util.BuildFactory()
    # set needed Propertys
    f.addStep(builders.SetupPropertys())
    # update the repositorys listed in project_repository
    f.addStep(builders.UpdateRepos())
    # Clean and add new /etc/portage
    #NOTE: remove the symlink befor the dir
    #f.addStep(buildbot_steps.ShellCommand(
    #                    flunkOnFailure=False,
    #                    name='Clean make.profile',
    #                    command=['rm', 'make.profile'],
    #                    workdir='/etc/portage/'
    #                    ))
    if buildbot_steps.FileExists(file='portage/make.conf', workdir='/etc/', haltOnFailure = False):
        f.addStep(buildbot_steps.ShellCommand(
                        flunkOnFailure=False,
                        name='Remove portage dir',
                        command=['rm', '-R', 'portage'],
                        workdir='/etc/'
                        ))
    f.addStep(buildbot_steps.ShellCommand(
                        flunkOnFailure=False,
                        name='Create portage dir',
                        command=['mkdir', 'portage'],
                        workdir='/etc/'
                        ))
    #f.addStep(buildbot_steps.RemoveDirectory(dir="portage",
    #                            name='Remove portage dir',
    #                            workdir='/etc/'))
    #f.addStep(buildbot_steps.MakeDirectory(dir="portage",
    #                            name = 'Create the portage dir',
    #                            workdir='/etc/'))
    # Clean /var/cache/portage/logs and emerge.log
    f.addStep(buildbot_steps.ShellCommand(
                        flunkOnFailure=False,
                        name='Clean emerge.log',
                        command=['rm', 'emerge.log'],
                        workdir='/var/log/'
                        ))
    if buildbot_steps.FileExists(file='logs', workdir='/var/cache/portage/',haltOnFailure = False):
        f.addStep(buildbot_steps.ShellCommand(
                        flunkOnFailure=False,
                        name='Remove logs',
                        command=['rm', '-R', 'logs'],
                        workdir='/var/cache/portage/'
                        ))
    # setup the profile
    #NOTE: pkgcheck do not support it as a dir
    #f.addStep(buildbot_steps.MakeDirectory(dir="make.profile",
    #                            workdir='/etc/portage/'))
    f.addStep(portage.SetMakeProfile())
    # setup repos.conf dir
    f.addStep(buildbot_steps.MakeDirectory(dir="repos.conf",
                                workdir='/etc/portage/'))
    f.addStep(portage.SetReposConf())
    # setup make.conf
    f.addStep(portage.SetMakeConf())
    # setup env
    f.addStep(portage.SetEnvDefault())
    # setup package.*
    f.addStep(portage.SetPackageDefault())
    # setup files in /etc if needed
    # run --regen if needed on repo
    # check cpv match
    f.addStep(builders.RunEmerge(step='match'))
    # Setup the needed stages for update, pkgcheck and build
    f.addStep(builders.SetupStepts())
    return f

def parse_build_log():
    f = util.BuildFactory()
    # FIXME: 6
    # set needed Propertys
    f.addStep(logs.SetupPropertys())
    # pers the build log for info qa errors
    f.addStep(logs.SetupParserBuildLoger())
    #f.addStep(logs.ParserBuildLog())
    # pers the log from pkg check
    #f.addStep(logs.ParserPkgCheckLog())
    # Upload the log to the cloud and remove the log
    #f.addStep(logs.Upload())
    # check the sum log if we need to make a issue/bug/pr report
    # set it SUCCESS/FAILURE/WARNINGS
    f.addStep(logs.MakeIssue())
    # add sum log to buildbot log
    f.addStep(logs.setBuildbotLog())
    # pers the emerge info
    f.addStep(logs.ReadEmergeInfoLog())
    # add emerge info to log and db
    f.addStep(logs.setEmergeInfoLog())
    # add package info to log and db
    f.addStep(logs.setPackageInfoLog())
    # set BuildStatus
    f.addStep(logs.setBuildStatus())
    # setup things for the irc bot
    #f.addStep(logs.SetIrcInfo())
    return f

def run_build_stage4_request():
    f = util.BuildFactory()
    # set needed Propertys
    f.addStep(nodes.SetupPropertys())
    # set the needed steps for making the stage4
    f.addStep(nodes.SetupStage4Steps())
    return f
