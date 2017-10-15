from redteam import redteam

__author__ = 'Jason Callaway'
__email__ = 'jasoncallaway@fedoraproject.org'
__license__ = 'GNU Public License v2'
__version__ = '0.1'
__status__ = 'alpha'

class CyberTestLab(object):
    def __init__(self, **kwargs):
        self.redteam = redteam.RedTeam(debug=True,
                                       connect_to_trello=False,
                                       cache_dir='~/.redteam')
        self.sapi = redteam.SAPI.SAPI()

        self.repo_dir = '/repo'
        if kwargs.get('repo_dir'):
            self.repo_dir = kwargs['repo_dir']

        self.swap_path = '/fedora_swap'
        if kwargs.get('swap_path'):
            self.swap_path = kwargs['swap_path']

        self.repo_list = ['fedora', 'updates']
        if kwargs.get('repo_list'):
            self.repo_list = kwargs['repo_list']

        self.hardening_check = self.redteam.funcs.which('hardening-check')
        if kwargs.get('hardening_check'):
            self.hardening_check = kwargs['hardening_check']

        self.debug = False
        if kwargs.get('debug'):
            self.debug = kwargs['debug']

    def repo_sync(self, command):
        args = ''
        if 'reposync' in command:
            args = ' -p ' + self.repo_dir
        else:
            raise Exception('CyberTestLab: unsupported repo type: ' + command)
        sync_cmd = self.redteam.funcs.which(command) + args
        r = self.redteam.funcs.run_command(sync_cmd, 'syncing repos')

    def prep_swap(self):
        rm = self.redteam.funcs.which('rm')
        cmd = rm + ' -Rf ' + self.swap_path + '/*'
        r = self.redteam.funcs.run_command(cmd, 'clean up swap path')

    def prep_rpm(self, repo, rpm):
        cp = self.redteam.funcs.which('cp')
        cmd = cp + ' ' + self.repo_dir + '/' + \
              repo + '/' + rpm + ' ' + \
              self.swap_path
        r = self.redteam.funcs.run_command(cmd, 'cp rpm to swap_path')

        # crack the rpm open
        # cd = self.redteam.funcs.which('cd')
        rpm2cpio = self.redteam.funcs.which('rpm2cpio')
        cpio = self.redteam.funcs.which('cpio')
        cmd = '(cd ' + self.swap_path + ' && ' + rpm2cpio + ' ' + \
              rpm + ' | ' + cpio + ' -idm 2>&1 >/dev/null)'
        r = self.redteam.funcs.run_command(cmd, 'rpm2cpio pipe to cpio')

    def get_metadata(self, rpm):
        rpm_data = {}
        cmd = 'rpm -qip ' + self.swap_path + '/' + rpm
        # this is a list
        rpm_qip = self.redteam.funcs.run_command(cmd, 'rpm -qip')

        not_description, description = \
            rpm_qip.split('Description :')
        raw_metadata = not_description.split('\n')
        metadata = {}
        for line in raw_metadata:
            if line == '':
                continue
            k, v = line.split(':', 1)
            metadata[k.rstrip()] = v
        metadata['Description'] = description
        rpm_data['spec_data'] = metadata

        return rpm_data

    def find_elfs(self, **kwargs):
        swap_path = self.swap_path
        if kwargs.get('swap_path'):
            swap_path = kwargs['swap_path']

        find_results = []
        find = self.redteam.funcs.which('find')
        grep = self.redteam.funcs.which('grep')
        cmd = find + ' ' + swap_path + \
              ' -type f -exec file {} \; | ' + grep + ' -i elf'
        find_results = self.redteam.funcs.run_command(cmd, 'find elfs')

        elfs = []
        for result in filter(None, find_results.split('\n')):
            elfs.append(result.split(':')[0])

        if len(elfs) == 0:
            return None
        else:
            return filter(None, elfs)

    def scan_elfs(self, rpm, elfs):
        if not elfs:
            raise Exception('scan_elfs: you gave me an empty list of elfs you dope')
        scan_results = {}
        
        for elf in elfs:
            binary = elf
            relative_binary = \
                binary.replace(self.swap_path + '/', '').replace('.', '_')

            scan_results[relative_binary] = {}
            scan_results[relative_binary]['rpm'] = rpm
            scan_results[relative_binary]['filename'] = binary.replace(
                self.swap_path + '/', '')

            # get hardening-check results
            cmd = self.hardening_check + ' ' + binary
            hardening_results = \
                self.redteam.funcs.run_command(cmd, 'hardening-check')

            # turn the hardening-check results into a dict
            pretty_results = {}
            for hr in hardening_results.split('\n'):
                if self.swap_path in hr:
                    continue
                if hr == '':
                    continue
                hrlist = hr.split(':')
                test = hrlist[0]
                finding = hrlist[1]
                pretty_results[test.rstrip()] = finding.rstrip().lstrip()
            scan_results[relative_binary]['hardening-check'] = pretty_results

            # get function report
            cmd = self.hardening_check + ' -R ' + binary
            hardening_results = \
                self.redteam.funcs.run_command(cmd, 'hardening-check -R')
            # relevant stuff starts at 9th line
            scan_results[relative_binary]['report-functions'] = \
                filter(None, hardening_results.split('\n')[8:])

            # get libc functions
            cmd = self.hardening_check + ' -F ' + binary
            hcdashf = filter(
                None,
                self.redteam.funcs.run_command(cmd,
                                               'hardening-check -F').split('\n')
            )
            hcdashf_clean = []
            for lib in hcdashf:
                hcdashf_clean.append(lib.split("'")[1])
            scan_results[relative_binary]['find-libc-functions'] = \
                hcdashf_clean

        return scan_results