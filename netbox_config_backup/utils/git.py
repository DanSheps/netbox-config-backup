import difflib
import re
import logging

logger = logging.getLogger(f"netbox_config_backup")


class Differ(difflib.Differ):
    def plain_compare(self, a, b):
        """
        Use plain replace instead of fancy replace
        :param a:
        :param b:
        :return:
        """

        cruncher = difflib.SequenceMatcher(self.linejunk, a, b)
        for tag, alo, ahi, blo, bhi in cruncher.get_opcodes():
            if tag == 'replace':
                g = self._plain_replace(a, alo, ahi, b, blo, bhi)
            elif tag == 'delete':
                g = self._dump('-', a, alo, ahi)
            elif tag == 'insert':
                g = self._dump('+', b, blo, bhi)
            elif tag == 'equal':
                g = self._dump(' ', a, alo, ahi)
            else:
                raise ValueError('unknown tag %r' % (tag,))

            yield from g

    def is_diff(self, a, b):
        diff = list(self.plain_compare(a, b))
        for row in diff:
            mode = row[0:1] if row[0:1] in ['+', '-'] else ''
            if mode in ['+', '-']:
                return True

        return False

    def cisco_compare(self, a, b, text=True):
        diff = list(self.plain_compare(a, b))
        output = []
        context = []
        for row in diff:
            mode = row[0:1] if row[0:1] in ['+', '-'] else ''
            line = row[2:]

            match = re.search(r'^(?P<depth>\s*).*', line)
            if match is not None:
                depth = len(match.groupdict().get('depth', ''))
            else:
                depth = 0

            ctx = {'line': line, 'depth': depth}
            if mode in ['+', '-']:
                context = list(filter(lambda x: x.get('depth') < depth, context))
                while len(context) > 0:
                    if text is True:
                        output.append(f'  {context.pop(0).get("line", "")}')
                    else:
                        output.append({'mode': mode, 'line': f'{context.pop(0).get("line", "")}'})
                if text is True:
                    output.append(f'{mode} {line}')
                else:
                    output.append({'mode': mode, 'line': f'{line}'})
            elif depth == 0:
                context = [ctx]
            elif len(context) > 0 and depth == context[-1].get('depth'):
                context.pop(-1)
                context.append(ctx)
            elif len(context) > 0 and depth > context[-1].get('depth'):
                context.append(ctx)
            elif len(context) > 0 and depth < context[-1].get('depth'):
                context = list(filter(lambda x: x.get('depth') < depth, context))
                context.append(ctx)

        return output
