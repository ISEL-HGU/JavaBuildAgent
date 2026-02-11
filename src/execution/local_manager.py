import os
import shutil
import subprocess
from src.utils.logger import logger

class LocalManager:
    def __init__(self, workspace_path: str, env_config: dict, build_relative_path: str = ""):
        self.workspace_path = workspace_path
        self.env_config = env_config
        self.build_relative_path = build_relative_path
        
        # Define tool paths
        self.tmp_root = "/data2/donggyu/benchmark/sec_code/tmp"
        self.jdk8_home = os.path.join(self.tmp_root, "jdks", "temurin8")
        self.jdk17_home = os.path.join(self.tmp_root, "jdks", "temurin17")
        self.maven_home = os.path.join(self.tmp_root, "maven")
        self.gradle_home = os.path.join(self.tmp_root, "gradle")
        
        self._validate_tools()

    def _validate_tools(self):
        """
        Validates that required tools exist in the tmp directory.
        """
        required_paths = [
            self.jdk8_home,
            self.jdk17_home,
            self.maven_home,
            self.gradle_home
        ]
        
        for path in required_paths:
            if not os.path.exists(path):
                logger.warning(f"Tool path not found: {path}. Local execution might fail if this tool is needed.")

    def execute(self, output_path: str = None) -> tuple[bool, str]:
        """
        Orchestrates the build process locally.
        Returns:
            (success: bool, logs: str)
        """
        logs = ""
        try:
            self._clean_target_on_host()
            exit_code, build_logs = self._run_build()
            logs = build_logs
            
            if exit_code == 0:
                if output_path:
                    self._extract_artifacts(output_path)
                return True, logs
            else:
                return False, logs
                
        except Exception as e:
            logger.error(f"Execution failed with exception: {e}")
            return False, str(e)

    def _clean_target_on_host(self):
        """
        Cleans the target directory on the host.
        """
        target_dir_mvn = os.path.join(self.workspace_path, self.build_relative_path, "target")
        target_dir_gradle = os.path.join(self.workspace_path, self.build_relative_path, "build")
        
        for target_dir in [target_dir_mvn, target_dir_gradle]:
            if os.path.exists(target_dir):
                logger.info(f"Cleaning target directory: {target_dir}")
                try:
                    shutil.rmtree(target_dir)
                except Exception as e:
                    logger.warning(f"Failed to clean target directory: {e}")

    def _run_build(self):
        """
        Runs the build using subprocess.
        Returns:
            (exit_code: int, logs: str, build_success: bool)
        """
        logger.info("Running build locally...")
        
        build_tool = self.env_config.get("build_tool", "maven")
        jdk_version = self.env_config.get("jdk_version", 8)
        
        # Set up environment variables
        env = os.environ.copy()
        
        # Set JAVA_HOME
        if str(jdk_version) == "17":
            java_home = self.jdk17_home
        else:
            java_home = self.jdk8_home
            
        env["JAVA_HOME"] = java_home
        
        # Update PATH to include JAVA_HOME/bin
        # We prepend to ensure our tools are used first
        path_elements = [os.path.join(java_home, "bin")]
        
        cmd = []
        cwd = os.path.join(self.workspace_path, self.build_relative_path)
        
        if build_tool == "gradle":
            # Gradle binary might be in bin or subfolder/bin
            gradle_bin_path = os.path.join(self.gradle_home, "bin", "gradle")
            if not os.path.exists(gradle_bin_path):
                 # Search for it
                 found = False
                 for root, dirs, files in os.walk(self.gradle_home):
                     if "gradle" in files and os.path.basename(os.path.dirname(os.path.join(root, "gradle"))) == "bin":
                         gradle_bin_path = os.path.join(root, "gradle")
                         found = True
                         break
                 if not found:
                     return -1, f"Gradle binary not found in {self.gradle_home}"
            
            cmd = [gradle_bin_path, "compileJava", "-x", "test", "--stacktrace", "--info"]
            
            # Inject init.gradle if needed
            init_gradle_src = os.path.join(os.path.dirname(__file__), "templates", "init.gradle")
            if os.path.exists(init_gradle_src):
                init_gradle_dst = os.path.join(self.workspace_path, "init.gradle")
                shutil.copy(init_gradle_src, init_gradle_dst)
                cmd.extend(["--init-script", init_gradle_dst])
                
            path_elements.append(os.path.dirname(gradle_bin_path))

        elif build_tool == "maven":
            mvn_bin_path = os.path.join(self.maven_home, "bin", "mvn")
            if not os.path.exists(mvn_bin_path):
                 # Search for it
                 found = False
                 for root, dirs, files in os.walk(self.maven_home):
                     if "mvn" in files and os.path.basename(os.path.dirname(os.path.join(root, "mvn"))) == "bin":
                         mvn_bin_path = os.path.join(root, "mvn")
                         found = True
                         break
                 if not found:
                     return -1, f"Maven binary not found in {self.maven_home}"

            cmd = [mvn_bin_path, "package", "-DskipTests", "-T", "1C"]
            
            # Handle exclusions
            exclusions = []
            distribution_path = os.path.join(cwd, "distribution")
            if os.path.exists(distribution_path):
                exclusions.append("!distribution")
            
            if exclusions:
                cmd.extend(["-pl", ",".join(exclusions)])
            
            cmd.extend(["-Dskip.npm=true", "-Dskip.node=true", "-Dskip.installnodenpm=true"])

            settings_xml = os.path.join(self.workspace_path, "settings.xml")
            if os.path.exists(settings_xml):
                cmd.extend(["-s", settings_xml])
                
            path_elements.append(os.path.dirname(mvn_bin_path))

        else:
            return -1, f"Unknown build tool: {build_tool}"

        # Finalize PATH
        env["PATH"] = os.pathsep.join(path_elements) + os.pathsep + env.get("PATH", "")
        
        logger.info(f"Command: {' '.join(cmd)}")
        logger.info(f"JAVA_HOME: {java_home}")
        logger.info(f"CWD: {cwd}")
        
        try:
            # Check permissions for binaries
            if build_tool == "gradle":
                 os.chmod(gradle_bin_path, 0o755)
            elif build_tool == "maven":
                 os.chmod(mvn_bin_path, 0o755)
                 
            process = subprocess.run(
                cmd,
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                check=False
            )
            
            logs = process.stdout + "\n" + process.stderr
            return process.returncode, logs
            
        except Exception as e:
            logger.error(f"Subprocess failed: {e}")
            return -1, str(e)

    def _extract_artifacts(self, output_path: str):
        """
        Copies the compiled artifacts (classes/jars) to the output directory.
        Same logic as DockerManager but local paths.
        """
        logger.info("Extracting artifacts...")
        
        source_classes_mvn = os.path.join(self.workspace_path, self.build_relative_path, "target", "classes")
        source_classes_gradle = os.path.join(self.workspace_path, self.build_relative_path, "build", "classes", "java", "main")
        
        source_classes = None
        if os.path.exists(source_classes_mvn):
            source_classes = source_classes_mvn
        elif os.path.exists(source_classes_gradle):
            source_classes = source_classes_gradle
        else:
            source_classes_gradle_legacy = os.path.join(self.workspace_path, self.build_relative_path, "build", "classes", "main")
            if os.path.exists(source_classes_gradle_legacy):
                source_classes = source_classes_gradle_legacy

        if not source_classes:
            logger.warning(f"No classes found at {source_classes_mvn} or {source_classes_gradle}")
            return
            
        dest_classes = os.path.join(output_path, "classes")
        
        if os.path.exists(dest_classes):
            shutil.rmtree(dest_classes)
            
        try:
            shutil.copytree(source_classes, dest_classes)
            logger.info(f"Artifacts extracted to {dest_classes}")
        except Exception as e:
            logger.error(f"Failed to extract artifacts: {e}")
