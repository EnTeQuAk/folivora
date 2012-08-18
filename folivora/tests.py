import pytz
import mock
from datetime import datetime
from django.test import TestCase
from django.utils.timezone import make_aware
from folivora.models import Package, PackageVersion, Project, Log, \
    ProjectDependency
from folivora import tasks


class CheesyMock(object):

    def get_package_list(self):
        return ['pmxbot']

    def get_changelog(self, hours, force=False):
        return [['pmxbot', '1101.8.1', 1345259834, 'new release']]

    def get_release_urls(self, name, version):
        return [{'comment_text': '',
                 'downloads': 0,
                 'filename': 'pmxbot-1101.8.1.zip',
                 'has_sig': False,
                 'md5_digest': '0a945fa5ea023036777b7cfde4518932',
                 'packagetype': 'sdist',
                 'python_version': 'source',
                 'size': 223006,
                 'upload_time': datetime.datetime(2012, 8, 18, 3, 17, 15),
                 'url': 'http://pypi.python.org/packages/source/p/pmxbot/pmxbot-1101.8.1.zip'}]


class TestPackageModel(TestCase):

    def setUp(self):
        pkg = Package.create_with_provider_url('pmxbot')
        project = Project.objects.create(name='test', slug='test')
        dependency = ProjectDependency.objects.create(
            project=project,
            package=pkg,
            version='1101.8.0')

    def test_creation(self):
        Package.objects.create(name='gunicorn',
                               url='http://pypi.python.org/pypi/gunicorn',
                               provider='pypi')
        pkg = Package.objects.get(name='gunicorn')
        self.assertEqual(pkg.name, 'gunicorn')
        self.assertEqual(pkg.url, 'http://pypi.python.org/pypi/gunicorn')
        self.assertEqual(pkg.provider, 'pypi')

    @mock.patch('folivora.tasks.CheeseShop', CheesyMock)
    def test_version_sync(self):
        pkg = Package.objects.get(name='pmxbot')
        self.assertEqual(pkg.versions.count(), 0)
        pkg.sync_versions()
        self.assertEqual(pkg.versions.count(), 1)
        version = pkg.versions.all()[0]
        self.assertEqual(version.version, '1101.8.1')


class TestPackageVersionModel(TestCase):

    def test_creation(self):
        Package.objects.create(name='gunicorn',
                               url='http://pypi.python.org/pypi/gunicorn',
                               provider='pypi')
        pkg = Package.objects.get(name='gunicorn')
        PackageVersion.objects.create(package=pkg,
                                      version='0.14.6',
                                      release_date=make_aware(datetime(2012, 7, 26, 23, 51, 18), pytz.UTC))
        vers = PackageVersion.objects.get(package__name='gunicorn',
                                          version='0.14.6')
        self.assertEqual(vers.package, pkg)
        self.assertEqual(vers.version, '0.14.6')
        self.assertEqual(vers.release_date,
                         make_aware(datetime(2012, 7, 26, 23, 51, 18), pytz.UTC))


class TestChangelogSync(TestCase):

    def setUp(self):
        pkg = Package.create_with_provider_url('pmxbot')
        self.project = Project.objects.create(name='test', slug='test')
        dependency = ProjectDependency.objects.create(
            project=self.project,
            package=pkg,
            version='1101.8.0')

    @mock.patch('folivora.tasks.CheeseShop', CheesyMock)
    def test_new_release_sync(self):
        result = tasks.sync_with_changelog.apply(throw=True)
        self.assertTrue(result.successful())
        pkg = Package.objects.get(name='pmxbot')
        self.assertEqual(pkg.name, 'pmxbot')
        self.assertEqual(pkg.provider, 'pypi')
        self.assertEqual(pkg.versions.count(), 1)

    @mock.patch('folivora.tasks.CheeseShop', CheesyMock)
    def test_new_release_sync_dependency_update(self):
        result = tasks.sync_with_changelog.apply(throw=True)
        self.assertTrue(result.successful())
        dep = ProjectDependency.objects.get(package__name='pmxbot', version='1101.8.0', project__name='test')
        self.assertEqual(dep.update.version, '1101.8.1')

    @mock.patch('folivora.tasks.CheeseShop', CheesyMock)
    def test_new_release_sync_log_creation(self):
        result = tasks.sync_with_changelog.apply(throw=True)
        self.assertTrue(result.successful())
        self.assertEqual(Log.objects.filter(project=self.project, action='new_release') \
                                    .count(),
                         1)
