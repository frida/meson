# Copyright 2014-2016 The Meson development team

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from . import backends
from .. import build
from .. import mesonlib
from .. import mlog
from .. import compilers
import uuid, os, sys
from ..compilers import CompilerArgs

from ..mesonlib import MesonException

class XCodeBackend(backends.Backend):
    def __init__(self, build):
        super().__init__(build)
        self.name = 'xcode'
        self.project_uid = self.environment.coredata.guid.replace('-', '')[:24]
        self.project_conflist = self.gen_id()
        self.indent = '       '
        self.indent_level = 0
        self.maingroup_id = self.gen_id()
        self.all_id = self.gen_id()
        self.all_buildconf_id = self.gen_id()
        self.buildtypes = ['debug']
        self.test_id = self.gen_id()
        self.test_command_id = self.gen_id()
        self.test_buildconf_id = self.gen_id()

    def generate(self, interp):
        self.interpreter = interp
        test_data = self.serialize_tests()[0]
        self.generate_filemap()
        self.generate_buildmap()
        self.generate_buildstylemap()
        self.generate_build_phase_map()
        self.generate_build_configuration_map()
        self.generate_build_configurationlist_map()
        self.generate_project_configurations_map()
        self.generate_buildall_configurations_map()
        self.generate_test_configurations_map()
        self.generate_native_target_map()
        self.generate_source_phase_map()
        self.generate_target_dependency_map()
        self.generate_pbxdep_map()
        self.generate_containerproxy_map()
        self.proj_dir = os.path.join(self.environment.get_build_dir(), self.build.project_name + '.xcodeproj')
        os.makedirs(self.proj_dir, exist_ok=True)
        self.proj_file = os.path.join(self.proj_dir, 'project.pbxproj')
        with open(self.proj_file, 'w') as self.ofile:
            self.generate_prefix()
            self.generate_pbx_aggregate_target()
            self.generate_pbx_build_file()
            self.generate_pbx_build_style()
            self.generate_pbx_container_item_proxy()
            self.generate_pbx_file_reference()
            self.generate_pbx_group()
            self.generate_pbx_native_target()
            self.generate_pbx_project()
            self.generate_pbx_shell_build_phase(test_data)
            self.generate_pbx_sources_build_phase()
            self.generate_pbx_target_dependency()
            self.generate_xc_build_configuration()
            self.generate_xc_configurationList()
            self.generate_suffix()

    def get_type_for_filename(self, filename):
        if not hasattr(self, 'type_map'):
            self.type_map = {'c': 'sourcecode.c.c',
                             'a': 'archive.ar',
                             'cc': 'sourcecode.cpp.cpp',
                             'cxx': 'sourcecode.cpp.cpp',
                             'cpp': 'sourcecode.cpp.cpp',
                             'c++': 'sourcecode.cpp.cpp',
                             'm': 'sourcecode.c.objc',
                             'mm': 'sourcecode.cpp.objcpp',
                             'h': 'sourcecode.c.h',
                             'hpp': 'sourcecode.cpp.h',
                             'hxx': 'sourcecode.cpp.h',
                             'hh': 'sourcecode.cpp.hh',
                             'inc': 'sourcecode.c.h',
                             'dylib': 'compiled.mach-o.dylib',
                             'o': 'compiled.mach-o.objfile',
                             'S': 'sourcecode.asm',
                             'js': 'sourcecode.javascript'
                            }

        extension = filename.split('.')[-1]

        if not extension in self.type_map:
            mlog.warning('Unknown extension: %s for file %s' %(extension, filename))
            return 'compiled'

        return self.type_map[extension]

    def gen_id(self):
        return str(uuid.uuid4()).upper().replace('-', '')[:24]

    def get_target_dir(self, target):
        dirname = os.path.join(target.get_subdir(), self.environment.coredata.get_builtin_option('buildtype'))
        os.makedirs(os.path.join(self.environment.get_build_dir(), dirname), exist_ok=True)
        return dirname

    def write_line(self, text):
        self.ofile.write(self.indent * self.indent_level + text)
        if not text.endswith('\n'):
            self.ofile.write('\n')

    def generate_filemap(self):
        self.filemap = {} # Key is source file relative to src root.
        self.target_filemap = {}
        for target_name, target in self.build.targets.items():
            for source in target.sources:
                if isinstance(source, mesonlib.File):
                    source = os.path.join(source.subdir, source.fname)
                    self.filemap[source] = self.gen_id()
                elif isinstance(source, str):
                    source = os.path.join(target.subdir, source)
                    self.filemap[source] = self.gen_id()
                else:
                    mlog.warning('Unknown type for source %s' % source)

                if hasattr(target, 'objects'):
                    for target_object in target.objects:
                        if isinstance(target_object, str):
                            target_object = os.path.join(target.subdir, target_object)
                            self.filemap[target_object] = self.gen_id()
                self.target_filemap[target_name] = self.gen_id()

    def generate_buildmap(self):
        self.buildmap = {}
        for target in self.build.targets.values():
            for source in target.sources:
                if isinstance(source, mesonlib.File):
                    source = os.path.join(source.subdir, source.fname)
                    self.buildmap[source] = self.gen_id()
                elif isinstance(source, str):
                    source = os.path.join(target.subdir, source)
                    self.buildmap[source] = self.gen_id()
                else:
                    mlog.warning('Unknown type for source %s' % source)

                if hasattr(target, 'objects'):
                    for target_object in target.objects:
                        target_object = os.path.join(target.subdir, target_object)
                        if isinstance(target_object, str):
                            self.buildmap[target_object] = self.gen_id()

    def generate_buildstylemap(self):
        self.buildstylemap = {'debug': self.gen_id()}

    def generate_build_phase_map(self):
        self.buildphasemap = {}
        for t in self.build.targets:
            self.buildphasemap[t] = self.gen_id()

    def generate_build_configuration_map(self):
        self.buildconfmap = {}
        for t in self.build.targets:
            bconfs = {'debug': self.gen_id()}
            self.buildconfmap[t] = bconfs

    def generate_project_configurations_map(self):
        self.project_configurations = {'debug': self.gen_id()}

    def generate_buildall_configurations_map(self):
        self.buildall_configurations = {'debug': self.gen_id()}

    def generate_test_configurations_map(self):
        self.test_configurations = {'debug': self.gen_id()}

    def generate_build_configurationlist_map(self):
        self.buildconflistmap = {}
        for t in self.build.targets:
            self.buildconflistmap[t] = self.gen_id()

    def generate_native_target_map(self):
        self.native_targets = {}
        for t in self.build.targets:
            self.native_targets[t] = self.gen_id()

    def generate_target_dependency_map(self):
        self.target_dependency_map = {}
        for target_name, target in self.build.targets.items():
            if isinstance(target, build.CustomTarget):
                for dependency in target.get_target_dependencies():
                    self.target_dependency_map[(target_name, dependency.get_basename())] = self.gen_id()
            else:
                for link_target in target.link_targets:
                    self.target_dependency_map[(target_name, link_target.get_basename())] = self.gen_id()

    def generate_pbxdep_map(self):
        self.pbx_dep_map = {}
        for t in self.build.targets:
            self.pbx_dep_map[t] = self.gen_id()

    def generate_containerproxy_map(self):
        self.containerproxy_map = {}
        for t in self.build.targets:
            self.containerproxy_map[t] = self.gen_id()

    def generate_source_phase_map(self):
        self.source_phase = {}
        for t in self.build.targets:
            self.source_phase[t] = self.gen_id()

    def generate_pbx_aggregate_target(self):
        self.ofile.write('\n/* Begin PBXAggregateTarget section */\n')
        self.write_line('%s /* ALL_BUILD */ = {' % self.all_id)
        self.indent_level += 1
        self.write_line('isa = PBXAggregateTarget;')
        self.write_line('buildConfigurationList = %s;' % self.all_buildconf_id)
        self.write_line('buildPhases = (')
        self.write_line(');')
        self.write_line('dependencies = (')
        self.indent_level += 1
        for t in self.build.targets:
            self.write_line('%s /* PBXTargetDependency */,' % self.pbx_dep_map[t])
        self.indent_level -= 1
        self.write_line(');')
        self.write_line('name = ALL_BUILD;')
        self.write_line('productName = ALL_BUILD;')
        self.indent_level -= 1
        self.write_line('};')
        self.write_line('%s /* RUN_TESTS */ = {' % self.test_id)
        self.indent_level += 1
        self.write_line('isa = PBXAggregateTarget;')
        self.write_line('buildConfigurationList = %s;' % self.test_buildconf_id)
        self.write_line('buildPhases = (')
        self.indent_level += 1
        self.write_line('%s /* test run command */,' % self.test_command_id)
        self.indent_level -= 1
        self.write_line(');')
        self.write_line('dependencies = (')
        self.write_line(');')
        self.write_line('name = RUN_TESTS;')
        self.write_line('productName = RUN_TESTS;')
        self.indent_level -= 1
        self.write_line('};')
        self.ofile.write('/* End PBXAggregateTarget section */\n')

    def generate_pbx_build_file(self):
        self.ofile.write('\n/* Begin PBXBuildFile section */\n')
        templ = '%s /* %s */ = { isa = PBXBuildFile; fileRef = %s /* %s */; settings = { COMPILER_FLAGS = "%s"; }; };\n'
        otempl = '%s /* %s */ = { isa = PBXBuildFile; fileRef = %s /* %s */;};\n'
        for target in self.build.targets.values():
            for source in target.sources:
                if isinstance(source, mesonlib.File):
                    source = source.fname

                if isinstance(source, str):
                    source = os.path.join(target.subdir, source)
                    idval = self.buildmap[source]
                    fullpath = os.path.join(self.environment.get_source_dir(), source)
                    fileref = self.filemap[source]
                    fullpath2 = fullpath
                    compiler_args = ''
                    self.ofile.write(templ % (idval, fullpath, fileref, fullpath2, compiler_args))
            if hasattr(target, 'objects'):
                for target_object in target.objects:
                    target_object = os.path.join(target.subdir, target_object)
                    idval = self.buildmap[target_object]
                    fileref = self.filemap[target_object]
                    fullpath = os.path.join(self.environment.get_source_dir(), target_object)
                    fullpath2 = fullpath
                    self.ofile.write(otempl % (idval, fullpath, fileref, fullpath2))
        self.ofile.write('/* End PBXBuildFile section */\n')

    def generate_pbx_build_style(self):
        self.ofile.write('\n/* Begin PBXBuildStyle section */\n')
        for name, idval in self.buildstylemap.items():
            self.write_line('%s /* %s */ = {\n' % (idval, name))
            self.indent_level += 1
            self.write_line('isa = PBXBuildStyle;\n')
            self.write_line('buildSettings = {\n')
            self.indent_level += 1
            self.write_line('COPY_PHASE_STRIP = NO;\n')
            self.indent_level -= 1
            self.write_line('};\n')
            self.write_line('name = "%s";\n' % name)
            self.indent_level -= 1
            self.write_line('};\n')
        self.ofile.write('/* End PBXBuildStyle section */\n')

    def generate_pbx_container_item_proxy(self):
        self.ofile.write('\n/* Begin PBXContainerItemProxy section */\n')
        for t in self.build.targets:
            self.write_line('%s /* PBXContainerItemProxy */ = {' % self.containerproxy_map[t])
            self.indent_level += 1
            self.write_line('isa = PBXContainerItemProxy;')
            self.write_line('containerPortal = %s /* Project object */;' % self.project_uid)
            self.write_line('proxyType = 1;')
            self.write_line('remoteGlobalIDString = %s;' % self.native_targets[t])
            self.write_line('remoteInfo = "%s";' % t)
            self.indent_level -= 1
            self.write_line('};')
        self.ofile.write('/* End PBXContainerItemProxy section */\n')

    def generate_pbx_file_reference(self):
        self.ofile.write('\n/* Begin PBXFileReference section */\n')
        src_templ = '%s /* %s */ = { isa = PBXFileReference; explicitFileType = "%s"; fileEncoding = 4; name = "%s"; path = "%s"; sourceTree = SOURCE_ROOT; };\n'
        for fname, idval in self.filemap.items():
            fullpath = os.path.join(self.environment.get_source_dir(), fname)
            xcodetype = self.get_type_for_filename(fname)
            name = os.path.split(fname)[-1]
            path = fname
            self.ofile.write(src_templ % (idval, fullpath, xcodetype, name, path))
        target_templ = '%s /* %s */ = { isa = PBXFileReference; explicitFileType = "%s"; path = %s; refType = %d; sourceTree = BUILT_PRODUCTS_DIR; };\n'
        for tname, idval in self.target_filemap.items():
            t = self.build.targets[tname]
            fname = t.get_filename()
            reftype = 0
            if isinstance(t, build.Executable):
                typestr = 'compiled.mach-o.executable'
                path = fname
            elif isinstance(t, build.SharedLibrary):
                typestr = self.get_type_for_filename('dummy.dylib')
                path = fname
            else:
                typestr = self.get_type_for_filename(fname)
                path = '"%s"' % t.get_filename()
            self.ofile.write(target_templ % (idval, tname, typestr, path, reftype))
        self.ofile.write('/* End PBXFileReference section */\n')

    def generate_pbx_group(self):
        groupmap = {}
        target_src_map = {}
        for target in self.build.targets:
            groupmap[target] = self.gen_id()
            target_src_map[target] = self.gen_id()
        self.ofile.write('\n/* Begin PBXGroup section */\n')
        sources_id = self.gen_id()
        resources_id = self.gen_id()
        products_id = self.gen_id()
        self.write_line('%s = {' % self.maingroup_id)
        self.indent_level += 1
        self.write_line('isa = PBXGroup;')
        self.write_line('children = (')
        self.indent_level += 1
        self.write_line('%s /* Sources */,' % sources_id)
        self.write_line('%s /* Resources */,' % resources_id)
        self.write_line('%s /* Products */,' % products_id)
        self.indent_level -= 1
        self.write_line(');')
        self.write_line('sourceTree = "<group>";')
        self.indent_level -= 1
        self.write_line('};')

        # Sources
        self.write_line('%s /* Sources */ = {' % sources_id)
        self.indent_level += 1
        self.write_line('isa = PBXGroup;')
        self.write_line('children = (')
        self.indent_level += 1
        for target in self.build.targets:
            self.write_line('%s /* %s */,' % (groupmap[target], target))
        self.indent_level -= 1
        self.write_line(');')
        self.write_line('name = Sources;')
        self.write_line('sourceTree = "<group>";')
        self.indent_level -= 1
        self.write_line('};')

        self.write_line('%s /* Resources */ = {' % resources_id)
        self.indent_level += 1
        self.write_line('isa = PBXGroup;')
        self.write_line('children = (')
        self.write_line(');')
        self.write_line('name = Resources;')
        self.write_line('sourceTree = "<group>";')
        self.indent_level -= 1
        self.write_line('};')

        # Targets
        for target_name, target in self.build.targets.items():
            self.write_line('%s /* %s */ = {' % (groupmap[target_name], target_name))
            self.indent_level += 1
            self.write_line('isa = PBXGroup;')
            self.write_line('children = (')
            self.indent_level += 1
            self.write_line('%s /* Source files */,' % target_src_map[target_name])
            self.indent_level -= 1
            self.write_line(');')
            self.write_line('name = "%s";' % target.get_basename())
            self.write_line('sourceTree = "<group>";')
            self.indent_level -= 1
            self.write_line('};')
            self.write_line('%s /* Source files */ = {' % target_src_map[target_name])
            self.indent_level += 1
            self.write_line('isa = PBXGroup;')
            self.write_line('children = (')
            self.indent_level += 1
            for source in target.sources:
                if isinstance(source, mesonlib.File):
                    source_path = os.path.join(source.subdir, source.fname)
                elif isinstance(source, str):
                    source_path = os.path.join(target.subdir, source)
                else:
                    mlog.warning('Unknown type for source %s' % source)

                self.write_line('%s /* %s */,' % (self.filemap[source_path], source_path))
            if hasattr(target, 'objects'):
                for target_object in target.objects:
                    target_object = os.path.join(target.subdir, target_object)
                    self.write_line('%s /* %s */,' % (self.filemap[target_object], target_object))
            self.indent_level -= 1
            self.write_line(');')
            self.write_line('name = "Source files";')
            self.write_line('sourceTree = "<group>";')
            self.indent_level -= 1
            self.write_line('};')

        # And finally products
        self.write_line('%s /* Products */ = {' % products_id)
        self.indent_level += 1
        self.write_line('isa = PBXGroup;')
        self.write_line('children = (')
        self.indent_level += 1
        for t in self.build.targets:
            self.write_line('%s /* %s */,' % (self.target_filemap[t], t))
        self.indent_level -= 1
        self.write_line(');')
        self.write_line('name = Products;')
        self.write_line('sourceTree = "<group>";')
        self.indent_level -= 1
        self.write_line('};')
        self.ofile.write('/* End PBXGroup section */\n')

    def generate_pbx_native_target(self):
        self.ofile.write('\n/* Begin PBXNativeTarget section */\n')
        for tname, idval in self.native_targets.items():
            target = self.build.targets[tname]
            self.write_line('%s /* %s */ = {' % (idval, tname))
            self.indent_level += 1

            if isinstance(target, build.CustomTarget):
                isa = 'PBXLegacyTarget'
            else:
                isa = 'PBXNativeTarget'

            self.write_line('isa = %s;' % isa)
            self.write_line('buildConfigurationList = %s /* Build configuration list for PBXNativeTarget "%s" */;'
                            % (self.buildconflistmap[tname], tname))
            self.write_line('buildPhases = (')
            self.indent_level += 1
            self.write_line('%s /* Sources */,' % self.buildphasemap[tname])
            self.indent_level -= 1
            self.write_line(');')
            self.write_line('buildRules = (')
            self.write_line(');')
            self.write_line('dependencies = (')
            self.indent_level += 1
            if hasattr(target, 'link_targets'):
                for link_target in self.build.targets[tname].link_targets:
                    # NOT DOCUMENTED, may need to make different links
                    # to same target have different targetdependency item.
                    idval = self.pbx_dep_map[link_target.get_id()]
                    self.write_line('%s /* PBXTargetDependency */,' % idval)
            self.indent_level -= 1
            self.write_line(");")
            self.write_line('name = "%s";' % target.get_basename())
            self.write_line('productName = "%s";' % tname)
            self.write_line('productReference = %s /* %s */;' % (self.target_filemap[tname], tname))
            if not isinstance(target, build.CustomTarget):
                if isinstance(target, build.Executable):
                    typestr = 'com.apple.product-type.tool'
                elif isinstance(target, build.StaticLibrary):
                    typestr = 'com.apple.product-type.library.static'
                elif isinstance(target, build.SharedLibrary):
                    typestr = 'com.apple.product-type.library.dynamic'
                else:
                    raise MesonException('Unknown target type for %s' % tname)
                self.write_line('productType = "%s";' % typestr)
            self.indent_level -= 1
            self.write_line('};')
        self.ofile.write('/* End PBXNativeTarget section */\n')

    def generate_pbx_project(self):
        self.ofile.write('\n/* Begin PBXProject section */\n')
        self.write_line('%s /* Project object */ = {' % self.project_uid)
        self.indent_level += 1
        self.write_line('isa = PBXProject;')
        self.write_line('attributes = {')
        self.indent_level += 1
        self.write_line('BuildIndependentTargetsInParallel = YES;')
        self.indent_level -= 1
        self.write_line('};')
        conftempl = 'buildConfigurationList = %s /* build configuration list for PBXProject "%s"*/;'
        self.write_line(conftempl % (self.project_conflist, self.build.project_name))
        self.write_line('buildSettings = {')
        self.write_line('};')
        self.write_line('buildStyles = (')
        self.indent_level += 1
        for name, idval in self.buildstylemap.items():
            self.write_line('%s /* %s */,' % (idval, name))
        self.indent_level -= 1
        self.write_line(');')
        self.write_line('compatibilityVersion = "Xcode 3.2";')
        self.write_line('hasScannedForEncodings = 0;')
        self.write_line('mainGroup = %s;' % self.maingroup_id)
        self.write_line('projectDirPath = "%s";' % self.build_to_src)
        self.write_line('projectRoot = "";')
        self.write_line('targets = (')
        self.indent_level += 1
        self.write_line('%s /* ALL_BUILD */,' % self.all_id)
        self.write_line('%s /* RUN_TESTS */,' % self.test_id)
        for t in self.build.targets:
            self.write_line('%s /* %s */,' % (self.native_targets[t], t))
        self.indent_level -= 1
        self.write_line(');')
        self.indent_level -= 1
        self.write_line('};')
        self.ofile.write('/* End PBXProject section */\n')

    def generate_pbx_shell_build_phase(self, test_data):
        self.ofile.write('\n/* Begin PBXShellScriptBuildPhase section */\n')
        self.write_line('%s = {' % self.test_command_id)
        self.indent_level += 1
        self.write_line('isa = PBXShellScriptBuildPhase;')
        self.write_line('buildActionMask = 2147483647;')
        self.write_line('files = (')
        self.write_line(');')
        self.write_line('inputPaths = (')
        self.write_line(');')
        self.write_line('outputPaths = (')
        self.write_line(');')
        self.write_line('runOnlyForDeploymentPostprocessing = 0;')
        self.write_line('shellPath = /bin/sh;')
        script_root = self.environment.get_script_dir()
        test_script = os.path.join(script_root, 'meson_test.py')
        cmd = [sys.executable, test_script, test_data, '--wd', self.environment.get_build_dir()]
        cmdstr = ' '.join(["'%s'" % i for i in cmd])
        self.write_line('shellScript = "%s";' % cmdstr)
        self.write_line('showEnvVarsInLog = 0;')
        self.indent_level -= 1
        self.write_line('};')
        self.ofile.write('/* End PBXShellScriptBuildPhase section */\n')

    def generate_pbx_sources_build_phase(self):
        self.ofile.write('\n/* Begin PBXSourcesBuildPhase section */\n')
        for name, phase_id in self.source_phase.items():
            self.write_line('%s /* Sources */ = {' % self.buildphasemap[name])
            self.indent_level += 1
            self.write_line('isa = PBXSourcesBuildPhase;')
            self.write_line('buildActionMask = 2147483647;')
            self.write_line('files = (')
            self.indent_level += 1
            target = self.build.targets[name]
            for source in target.sources:
                if isinstance(source, mesonlib.File):
                    source = os.path.join(source.subdir, source.fname)
                elif isinstance(source, str):
                    source = os.path.join(target.subdir, source)
                else:
                    mlog.warning('Unknown type for source %s' % source)
                    continue

                if not self.environment.is_header(source):
                    self.write_line('%s /* %s */,' % (self.buildmap[source], os.path.join(self.environment.get_source_dir(), source)))
            self.indent_level -= 1
            self.write_line(');')
            self.write_line('runOnlyForDeploymentPostprocessing = 0;')
            self.indent_level -= 1
            self.write_line('};')
        self.ofile.write('/* End PBXSourcesBuildPhase section */\n')

    def generate_pbx_target_dependency(self):
        self.ofile.write('\n/* Begin PBXTargetDependency section */\n')
        for t in self.build.targets:
            idval = self.pbx_dep_map[t] # VERIFY: is this correct?
            self.write_line('%s /* PBXTargetDependency */ = {' % idval)
            self.indent_level += 1
            self.write_line('isa = PBXTargetDependency;')
            self.write_line('target = %s /* %s */;' % (self.native_targets[t], t))
            self.write_line('targetProxy = %s /* PBXContainerItemProxy */;' % self.containerproxy_map[t])
            self.indent_level -= 1
            self.write_line('};')
        self.ofile.write('/* End PBXTargetDependency section */\n')

    def target_to_build_root(self, target):
        if target.subdir == '':
            return ''

        directories = os.path.normpath(target.subdir).split(os.sep)
        return os.sep.join(['..'] * len(directories))

    def generate_xc_build_configuration(self):
        self.ofile.write('\n/* Begin XCBuildConfiguration section */\n')
        # First the setup for the toplevel project.
        for buildtype in self.buildtypes:
            self.write_line('%s /* %s */ = {' % (self.project_configurations[buildtype], buildtype))
            self.indent_level += 1
            self.write_line('isa = XCBuildConfiguration;')
            self.write_line('buildSettings = {')
            self.indent_level += 1
            self.write_line('ARCHS = "$(ARCHS_STANDARD_32_64_BIT)";')
            self.write_line('ONLY_ACTIVE_ARCH = YES;')
            self.write_line('SDKROOT = "macosx";')
            self.write_line('SYMROOT = "%s/build";' % self.environment.get_build_dir())
            self.indent_level -= 1
            self.write_line('};')
            self.write_line('name = "%s";' % buildtype)
            self.indent_level -= 1
            self.write_line('};')

        # Then the all target.
        for buildtype in self.buildtypes:
            self.write_line('%s /* %s */ = {' % (self.buildall_configurations[buildtype], buildtype))
            self.indent_level += 1
            self.write_line('isa = XCBuildConfiguration;')
            self.write_line('buildSettings = {')
            self.indent_level += 1
            self.write_line('COMBINE_HIDPI_IMAGES = YES;')
            self.write_line('GCC_GENERATE_DEBUGGING_SYMBOLS = NO;')
            self.write_line('GCC_INLINES_ARE_PRIVATE_EXTERN = NO;')
            self.write_line('GCC_OPTIMIZATION_LEVEL = 0;')
            self.write_line('GCC_PREPROCESSOR_DEFINITIONS = ("");')
            self.write_line('GCC_SYMBOLS_PRIVATE_EXTERN = NO;')
            self.write_line('INSTALL_PATH = "";')
            self.write_line('OTHER_CFLAGS = "  ";')
            self.write_line('OTHER_LDFLAGS = " ";')
            self.write_line('OTHER_REZFLAGS = "";')
            self.write_line('PRODUCT_NAME = ALL_BUILD;')
            self.write_line('SECTORDER_FLAGS = "";')
            self.write_line('SYMROOT = "%s";' % self.environment.get_build_dir())
            self.write_line('USE_HEADERMAP = NO;')
            self.write_line('WARNING_CFLAGS = ("-Wmost", "-Wno-four-char-constants", "-Wno-unknown-pragmas", );')
            self.indent_level -= 1
            self.write_line('};')
            self.write_line('name = "%s";' % buildtype)
            self.indent_level -= 1
            self.write_line('};')

        # Then the test target.
        for buildtype in self.buildtypes:
            self.write_line('%s /* %s */ = {' % (self.test_configurations[buildtype], buildtype))
            self.indent_level += 1
            self.write_line('isa = XCBuildConfiguration;')
            self.write_line('buildSettings = {')
            self.indent_level += 1
            self.write_line('COMBINE_HIDPI_IMAGES = YES;')
            self.write_line('GCC_GENERATE_DEBUGGING_SYMBOLS = NO;')
            self.write_line('GCC_INLINES_ARE_PRIVATE_EXTERN = NO;')
            self.write_line('GCC_OPTIMIZATION_LEVEL = 0;')
            self.write_line('GCC_PREPROCESSOR_DEFINITIONS = ("");')
            self.write_line('GCC_SYMBOLS_PRIVATE_EXTERN = NO;')
            self.write_line('INSTALL_PATH = "";')
            self.write_line('OTHER_CFLAGS = "  ";')
            self.write_line('OTHER_LDFLAGS = " ";')
            self.write_line('OTHER_REZFLAGS = "";')
            self.write_line('PRODUCT_NAME = RUN_TESTS;')
            self.write_line('SECTORDER_FLAGS = "";')
            self.write_line('SYMROOT = "%s";' % self.environment.get_build_dir())
            self.write_line('USE_HEADERMAP = NO;')
            self.write_line('WARNING_CFLAGS = ("-Wmost", "-Wno-four-char-constants", "-Wno-unknown-pragmas", );')
            self.indent_level -= 1
            self.write_line('};')
            self.write_line('name = "%s";' % buildtype)
            self.indent_level -= 1
            self.write_line('};')

        # Now finally targets.
        langnamemap = {'c': 'C', 'cpp': 'CPLUSPLUS', 'objc': 'OBJC', 'objcpp': 'OBJCPLUSPLUS'}
        for target_name, target in self.build.targets.items():
            build_root = self.target_to_build_root(target)
            project_to_source_root = os.path.join(build_root, self.build_to_src)
            for buildtype in self.buildtypes:
                dep_libs = []
                links_dylib = False
                headerdirs = []
                headerdirs.append(self.environment.get_build_dir())
                if isinstance(target, build.CustomTarget):
                    directory = os.path.join(self.environment.get_source_dir(), self.get_target_dir(target))
                    headerdirs.append(directory)
                else:
                    for directories in reversed(target.get_include_dirs()):
                        for header_directory in directories.get_incdirs():
                            current_directory = os.path.join(directories.get_curdir(), header_directory)
                            directory = os.path.join(self.environment.get_source_dir(), current_directory)
                            headerdirs.append(directory)

                        for header_directory in directories.get_extra_build_dirs():
                            current_directory = os.path.join(directories.get_curdir(), header_directory)
                            directory = os.path.join(self.environment.get_build_dir(), current_directory)
                            headerdirs.append(directory)

                    for l in target.link_targets:
                        abs_path = os.path.join(self.environment.get_build_dir(),
                                                l.subdir, buildtype, l.get_filename())
                        dep_libs.append("'%s'" % abs_path)
                        if isinstance(l, build.SharedLibrary):
                            links_dylib = True
                if links_dylib:
                    dep_libs = ['-Wl,-search_paths_first', '-Wl,-headerpad_max_install_names'] + dep_libs
                dylib_version = None
                if isinstance(target, build.SharedLibrary):
                    ldargs = ['-dynamiclib', '-Wl,-headerpad_max_install_names'] + dep_libs
                    install_path = os.path.join(self.environment.get_build_dir(), target.subdir, buildtype)
                    dylib_version = target.soversion
                else:
                    ldargs = dep_libs
                    install_path = ''
                if dylib_version is not None:
                    product_name = target.get_basename() + '.' + dylib_version
                else:
                    product_name = target.get_basename()
                if hasattr(target, 'link_args'):
                    ldargs += target.link_args
                ldstr = ' '.join(ldargs)
                valid = self.buildconfmap[target_name][buildtype]
                langargs = {}
                for lang in self.environment.coredata.compilers:
                    if lang not in langnamemap:
                        continue
                    gargs = self.build.global_args.get(lang, [])
                    if not isinstance(target, build.CustomTarget):
                        targs = target.get_extra_args(lang)
                    else:
                        targs = []
                    args = gargs + targs
                    if len(args) > 0:
                        langargs[langnamemap[lang]] = args
                symroot = os.path.join(self.environment.get_build_dir(), target.subdir)
                self.write_line('%s /* %s */ = {' % (valid, buildtype))
                self.indent_level += 1
                self.write_line('isa = XCBuildConfiguration;')
                self.write_line('buildSettings = {')
                self.indent_level += 1
                self.write_line('COMBINE_HIDPI_IMAGES = YES;')
                if dylib_version is not None:
                    self.write_line('DYLIB_CURRENT_VERSION = "%s";' % dylib_version)
                if hasattr(target, 'prefix'):
                    self.write_line('EXECUTABLE_PREFIX = "%s";' % target.prefix)

                if hasattr(target, 'prefix'):
                    if target.suffix == '':
                        suffix = ''
                    else:
                        suffix = '.' + target.suffix
                else:
                    suffix = ''

                # Extra compile arguments
                if not isinstance(target, build.CustomTarget):
                    file_args = dict((lang, CompilerArgs(comp)) for lang, comp in target.compilers.items())
                    file_defines = dict((lang, []) for lang in target.compilers)
                    file_inc_dirs = dict((lang, []) for lang in target.compilers)
                    target_defines = []
                    target_args = []
                    for l, comp in target.compilers.items():
                        if l in file_args:
                            file_args[l] += compilers.get_base_compile_args(self.environment.coredata.base_options, comp)
                            file_args[l] += comp.get_option_compile_args(self.environment.coredata.compiler_options)

                    for l, args in self.build.projects_args.get(target.subproject, {}).items():
                        if l in file_args:
                            file_args[l] += args

                    for l, args in self.build.global_args.items():
                        if l in file_args:
                            file_args[l] += args
                    if not target.is_cross:
                        # Compile args added from the env: CFLAGS/CXXFLAGS, etc. We want these
                        # to override all the defaults, but not the per-target compile args.
                        for l, args in self.environment.coredata.external_args.items():
                            if l in file_args:
                                file_args[l] += args
                    # Add per-target compile args, f.ex, `c_args : ['-DFOO']`. We set these
                    # near the end since these are supposed to override everything else.
                    for l, args in target.extra_args.items():
                        if l in file_args:
                            file_args[l] += args

                    # Split preprocessor defines and include directories out of the list of
                    # all extra arguments. The rest go into %(AdditionalOptions).
                    for l, args in file_args.items():
                        for arg in args[:]:
                            if arg.startswith('-I'):
                                file_args[l].remove(arg)
                                inc_dir = arg[2:]
                                # De-dup
                                if inc_dir not in headerdirs:
                                    headerdirs.append(inc_dir)

                    compiler = self._get_cl_compiler(target)
                    for d in reversed(target.get_external_deps()):
                        d_compile_args = compiler.unix_args_to_native(d.get_compile_args())
                        for arg in d_compile_args:
                            if arg.startswith('-I'):
                                inc_dir = arg[2:]
                                # De-dup
                                if inc_dir not in headerdirs:
                                    headerdirs.append(inc_dir)
                            else:
                                if arg not in file_args:
                                    target_args.append(arg)

                if 'c' in file_args:
                    c_flags = ' '.join(file_args['c']).replace('"', '\\\\\\"')
                    self.write_line('OTHER_CFLAGS = "%s";' % c_flags)

                self.write_line('EXECUTABLE_SUFFIX = "%s";' % suffix)
                self.write_line('GCC_GENERATE_DEBUGGING_SYMBOLS = YES;')
                self.write_line('GCC_INLINES_ARE_PRIVATE_EXTERN = NO;')
                self.write_line('GCC_OPTIMIZATION_LEVEL = 0;')
                self.write_line('GCC_PREPROCESSOR_DEFINITIONS = ("");')
                self.write_line('GCC_SYMBOLS_PRIVATE_EXTERN = NO;')
                if len(headerdirs) > 0:
                    quotedh = ','.join(['"\\"%s\\""' % i for i in headerdirs])
                    self.write_line('HEADER_SEARCH_PATHS=(%s);' % quotedh)
                self.write_line('INSTALL_PATH = "%s";' % install_path)
                self.write_line('LIBRARY_SEARCH_PATHS = "";')
                if isinstance(target, build.SharedLibrary):
                    self.write_line('LIBRARY_STYLE = DYNAMIC;')
                for langname, args in langargs.items():
                    argstr = ' '.join(args)
                    self.write_line('OTHER_%sFLAGS = "%s";' % (langname, argstr))
                self.write_line('OTHER_LDFLAGS = "%s";' % ldstr)
                self.write_line('OTHER_REZFLAGS = "";')
                self.write_line('PRODUCT_NAME = %s;' % product_name)
                self.write_line('SECTORDER_FLAGS = "";')
                self.write_line('SYMROOT = "%s";' % symroot)
                self.write_line('USE_HEADERMAP = NO;')
                self.write_line('WARNING_CFLAGS = ("-Wmost", "-Wno-four-char-constants", "-Wno-unknown-pragmas", );')
                self.indent_level -= 1
                self.write_line('};')
                self.write_line('name = "%s";' % buildtype)
                self.indent_level -= 1
                self.write_line('};')
        self.ofile.write('/* End XCBuildConfiguration section */\n')

    def generate_xc_configurationList(self):
        self.ofile.write('\n/* Begin XCConfigurationList section */\n')
        self.write_line('%s /* Build configuration list for PBXProject "%s" */ = {' % (self.project_conflist, self.build.project_name))
        self.indent_level += 1
        self.write_line('isa = XCConfigurationList;')
        self.write_line('buildConfigurations = (')
        self.indent_level += 1
        for buildtype in self.buildtypes:
            self.write_line('%s /* %s */,' % (self.project_configurations[buildtype], buildtype))
        self.indent_level -= 1
        self.write_line(');')
        self.write_line('defaultConfigurationIsVisible = 0;')
        self.write_line('defaultConfigurationName = debug;')
        self.indent_level -= 1
        self.write_line('};')

        # Now the all target
        self.write_line('%s /* Build configuration list for PBXAggregateTarget "ALL_BUILD" */ = {' % self.all_buildconf_id)
        self.indent_level += 1
        self.write_line('isa = XCConfigurationList;')
        self.write_line('buildConfigurations = (')
        self.indent_level += 1
        for buildtype in self.buildtypes:
            self.write_line('%s /* %s */,' % (self.buildall_configurations[buildtype], buildtype))
        self.indent_level -= 1
        self.write_line(');')
        self.write_line('defaultConfigurationIsVisible = 0;')
        self.write_line('defaultConfigurationName = debug;')
        self.indent_level -= 1
        self.write_line('};')

        # Test target
        self.write_line('%s /* Build configuration list for PBXAggregateTarget "ALL_BUILD" */ = {' % self.test_buildconf_id)
        self.indent_level += 1
        self.write_line('isa = XCConfigurationList;')
        self.write_line('buildConfigurations = (')
        self.indent_level += 1
        for buildtype in self.buildtypes:
            self.write_line('%s /* %s */,' % (self.test_configurations[buildtype], buildtype))
        self.indent_level -= 1
        self.write_line(');')
        self.write_line('defaultConfigurationIsVisible = 0;')
        self.write_line('defaultConfigurationName = debug;')
        self.indent_level -= 1
        self.write_line('};')

        for target_name in self.build.targets:
            listid = self.buildconflistmap[target_name]
            self.write_line('%s /* Build configuration list for PBXNativeTarget "%s" */ = {' % (listid, target_name))
            self.indent_level += 1
            self.write_line('isa = XCConfigurationList;')
            self.write_line('buildConfigurations = (')
            self.indent_level += 1
            typestr = 'debug'
            idval = self.buildconfmap[target_name][typestr]
            self.write_line('%s /* %s */,' % (idval, typestr))
            self.indent_level -= 1
            self.write_line(');')
            self.write_line('defaultConfigurationIsVisible = 0;')
            self.write_line('defaultConfigurationName = "%s";' % typestr)
            self.indent_level -= 1
            self.write_line('};')
        self.ofile.write('/* End XCConfigurationList section */\n')

    def generate_prefix(self):
        self.ofile.write('// !$*UTF8*$!\n{\n')
        self.indent_level += 1
        self.write_line('archiveVersion = 1;\n')
        self.write_line('classes = {\n')
        self.write_line('};\n')
        self.write_line('objectVersion = 46;\n')
        self.write_line('objects = {\n')
        self.indent_level += 1

    def generate_suffix(self):
        self.indent_level -= 1
        self.write_line('};\n')
        self.write_line('rootObject = ' + self.project_uid + ';')
        self.indent_level -= 1
        self.write_line('}\n')

    def _get_cl_compiler(self, target):
        for lang, c in target.compilers.items():
            if lang in ('c', 'cpp'):
                return c
        # No source files, only objects, but we still need a compiler, so
        # return a found compiler
        if len(target.objects) > 0:
            for lang, c in self.environment.coredata.compilers.items():
                if lang in ('c', 'cpp'):
                    return c
        raise MesonException('Could not find a C or C++ compiler.')
