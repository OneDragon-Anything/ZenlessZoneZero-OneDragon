from one_dragon.base.config.yaml_config import YamlConfig


class ProjectConfig(YamlConfig):

    def __init__(self):
        YamlConfig.__init__(self, module_name='project')

        self.project_name = self.get('project_name')
        self.python_version = self.get('python_version')
        self.github_homepage = self.get('github_homepage')
        self.github_https_repository = self.get('github_https_repository')
        self.github_ssh_repository = self.get('github_ssh_repository')
        self.gitee_https_repository = self.get('gitee_https_repository')
        self.gitee_ssh_repository = self.get('gitee_ssh_repository')
        self.project_git_branch = self.get('project_git_branch')
        self.requirements = self.get('requirements')

        self.screen_standard_width = int(self.get('screen_standard_width'))
        self.screen_standard_height = int(self.get('screen_standard_height'))

        self.qq_link = self.get('qq_link')
        self.quick_start_link = self.get('quick_start_link')  # 链接 - 快速开始
