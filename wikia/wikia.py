import discord
from redbot.core import commands, Config, checks
from redbot.core.utils.chat_formatting import escape
import aiohttp
import asyncio
import os
import re
import string
import traceback
import urllib.parse

find_whitespace = re.compile("\\s")
match_file_options = re.compile('|'.join(['border', 'frameless', 'frame', 'thumb', 'thumbnail',
                        '\d+px', 'x\d+px', '\d+x\d+px', 'upright',
                        'left', 'right', 'center', 'none',
                        'baseline', 'sub', 'super', 'top', 'text-top', 'middle', 'bottom', 'text-bottom',
                        'link=.*', 'alt=.*', 'page=.*', 'class=.*', 'lang=.*']))

class Wikia(commands.Cog):
    """Command to view Wikia pages."""

    def __init__(self, bot):
        default_guild = {
                "default_wikia": '',
        }

        self.bot = bot
        self.config = Config.get_conf(self, identifier=0xff5269620002)
        self.config.register_guild(**default_guild)
        self.http_client = aiohttp.ClientSession()

    def __unload(self):
        self.http_client.close()

    @commands.command(aliases=["wiki"])
    async def wikia(self, ctx, *, search_terms : str):
        """Wikia lookup. Finds a Wikia page by name and displays it with formatting and images.
        
        Specify the Wikia to use (if it's different from the default one set for this server) by typing "-w" followed by the Wikia subdomain anywhere in the command.
        
        Alternatively, you may use a complete URL to an article to view the text and formatting on that page. Enclose it with <>s to avoid your own message generating a preview."""

        try:
            wikia, page_name, section_name  = await self.parse_search_terms(ctx, search_terms)
            if wikia is None:
                return

            fields = {}
            fields['search_state'] = 'title'
            result, fields                  = await self.wikia_api_get_page_content(wikia, page_name, section_name, search_fields=fields)
            if not result and fields['namespace'] != 'Category':
                fields['search_state'] = 'fuzzy'
                fields['search_input'] = page_name
                fields['search_results'], \
                  fields['search_warnings'] = await self.wikia_api_search_pages(wikia, page_name, 'fuzzy', 10)

                #print(str(fields['search_results']))
                if fields['search_results'] and len(fields['search_results']) == 1:
                    result, fields          = await self.wikia_api_get_page_content(wikia, fields['search_results'][0], section_name, search_fields=fields)
                    if not result:
                        fields['search_state'] = 'error_given_result_failed'
                elif fields['search_results'] and len(fields['search_results']) > 1:
                    fields['search_state'] = 'error_multiple_choices'
                else:
                    fields['search_state'] = 'error_no_results'

            if result:
                if fields['namespace'] == 'File' or fields['namespace'] == 'Image':
                    #print(page_name)
                    fields['im_details']        = await self.wikia_api_get_image_info(wikia, page_name, thumb_width = None)
                elif 'first_image' in fields:
                    if not fields['first_image'] is None:
                        #print(fields['first_image'][0])
                        fields['im_details']    = await self.wikia_api_get_image_info(wikia, fields['first_image'][0], thumb_width = 512)
                    #fields['im_serving']        = await self.wikia_api_get_image_serving_image(wikia, page_name)

            if fields['namespace'] == 'Category':
                fields['cat_members'], \
                      fields['cat_subcats'] = await self.wikia_api_get_category_members(wikia, page_name, 100)
                if len(fields['cat_members']) == 0 and len(fields['cat_subcats']) == 0 and not result:
                    fields['search_state'] = 'error_no_category'
                    del fields['cat_members']
                    del fields['cat_subcats']

            embed = self.wikia_embed_output(ctx, **fields)

            try:
                await ctx.send(embed=embed)
            except Exception as ex:
                print('Exception on sending discord.Embed:\n{}\n'.format(traceback.format_exc()))
                await ctx.send(escape('*Error: An error occurred sending the "Embed":* `{}`\n**__{}__{}** (<{}{}>):\n\n{}'.format(
                            str(ex),
                            fields['page_name'], 
                            fields['section_name_appender'],
                            fields['page_url'], 
                            fields['section_url'],
                            fields['page_content'])))
        except Exception as ex:
            print('Exception on ".wiki" command:\n{}\n'.format(traceback.format_exc()))
            await ctx.send('*Error: An error occurred processing the Wikia API:* `{}`'.format(escape(str(ex))))


    async def parse_search_terms(self, ctx, search_terms):
        """Parses the search terms into "wikia", "page_name", and "section_name" parts."""
        search_terms = search_terms.strip(' <>:\t\n')
        if search_terms.lower().startswith('http://') or search_terms.lower().startswith('https://') or search_terms.startswith('//'):
            subd_start = search_terms.find('/') + 2
            subd_end = search_terms.find('.', subd_start)
            search_start = search_terms.find('/', subd_start) + 1
        elif search_terms.lower().startswith('-w ') or search_terms.lower().startswith('-wiki '):
            subd_start = search_terms.find(' ') + 1
            subd_end = search_terms.find(' ', subd_start)
            search_start = subd_end + 1
        else:
            subd_start = -1
            subd_end = -1
            search_start = 0

        if subd_end >= 0 and subd_start >= 0:
            wikia = search_terms[subd_start:subd_end]
            search_terms = search_terms[search_start:].strip(' <>:\t\n')
            if search_terms.startswith('wiki/') or search_terms.startswith('w/'):
                search_start = search_terms.find('/') + 1
                search_terms = search_terms[search_start:].strip(' <>:\t\n')
        else:
            if ctx.guild is None:
                await ctx.send('*Error: You cannot set a default Wikia in private messages with me. You must use the command with a `-w`/`-wiki` parameter that specifies the Wikia to use.*')
                return None, None, None

            wikia = await self.config.guild(ctx.guild).default_wikia()
            if wikia is None or len(wikia) < 2:
                await ctx.send('*Error: No default Wikia has been set for this server. You must use the command with a `-w`/`-wiki` parameter that specifies the Wikia to use.*')
                return None, None, None

        if '#' in search_terms:
            parts = search_terms.split('#', 1)
            search_terms = parts[0].strip(' <>:\t\n')
            section = parts[1].strip(' <>:\t\n')
            section = self.normalize_section(section.replace('_', ' '))
        else:
            search_terms = search_terms.strip()
            section = None

        search_terms = search_terms.replace('_', ' ')
        return wikia, search_terms, section

    async def wikia_api_get(self, wikia, api_url):
        """Performs a Wikia API request."""
        base_url = 'https://{}.wikia.com/wiki/'.format(wikia)
        base_api_url = "https://{}.wikia.com/api.php?".format(wikia)
        url = '{}{}'.format(base_api_url, api_url)
        headers = {'User-Agent': 'WikiaReaderCog/1.0 MegamiBot/1.0 RedDiscordBot/1.0 DiscordPy/1.0'}
        result = None
        async with self.http_client.get(url, headers=headers) as r:
            result = await r.json()
        return result, base_url

    async def wikia_api_search_pages(self, wikia, page_name, profile = 'fuzzy', limit = 10):
        """Searches for a page by title using the Wikia API."""
        page_name_quoted = urllib.parse.quote(page_name)
        url = 'action=opensearch&search={}&namespace=&profile={}&redirects=resolve&limit={}&format=json'.format(page_name_quoted, profile, limit)
        result, base_url = await self.wikia_api_get(wikia, url)
        #print('search json: ```{}```'.format(result))

        warnings = None
        if 'warnings' in result:
            if 'opensearch' in result['warnings']:
                warnings = str(result['warnings']['opensearch'])

        if isinstance(result, list):
            return result[1], warnings
        elif '1' in result:
            return result['1'], warnings
        else:
            return [], warnings

    async def wikia_api_get_page_images(self, wikia, page_name, limit = 1):
        """Gets the "pageimage"s of a page using the Wikia API."""
        page_name_quoted = urllib.parse.quote(page_name)
        url = 'action=query&prop=images&titles={}&imlimit={}&format=json'.format(page_name_quoted, limit)
        result, base_url = await self.wikia_api_get(wikia, url)
        #print('pageimages json: ```{}```'.format(result))

        if not result is None and 'query' in result:
            if 'pages' in result['query']:
                #await ctx.send('```\r\n{}```'.format(result['query']['pages']))
                for key, value in result['query']['pages'].items():
                    if 'images' in value:
                        for img in value['images']:
                            if 'title' in img:
                                #print(img['title'])
                                pass
        return []

    async def wikia_api_get_page_content(self, wikia, page_name, section_name, search_fields = {}):
        """Gets the content of a page using the Wikia API."""
        page_name_quoted = urllib.parse.quote(page_name)
        url = 'action=query&titles={}&prop=revisions&rvprop=timestamp|flags|comment|user|size|content&format=json&redirects=1'.format(page_name_quoted)
        result, base_url = await self.wikia_api_get(wikia, url)

        fields = search_fields
        fields['found_content'] = False
        fields['wikia'] = wikia
        fields['base_url'] = base_url
        fields['page_name'] = page_name
        fields['namespace'] = self.wikia_get_namespace(page_name)
        fields['page_url'] = base_url + urllib.parse.quote(page_name.replace(' ', '_'))
        fields['section_name'] = section_name
        fields['page_content'] = ''
        if section_name and len(section_name) > 0:
            fields['section_name_appender'] = ' \u2192 {}'.format(section_name)
            fields['section_url'] = '#{}'.format(urllib.parse.quote(section_name.replace(' ', '_')).replace('%', '.'))
        else:
            fields['section_name_appender'] = ''
            fields['section_url'] = ''
        
        if not result is None and 'query' in result:
            fields['redirected'] = None
            if 'normalized' in result['query']:
                if len(result['query']['normalized']) > 0:
                    if 'to' in result['query']['normalized'][0]:
                        fields['page_name'] = result['query']['normalized'][0]['to']
            if 'redirects' in result['query']:
                if len(result['query']['redirects']) > 0:
                    if 'from' in result['query']['redirects'][0]:
                        fields['redirected'] = result['query']['redirects'][0]['from']
                    if 'to' in result['query']['redirects'][0]:
                        fields['page_name'] = result['query']['redirects'][0]['to']
            if 'pages' in result['query']:
                #await ctx.send('```\r\n{}```'.format(result['query']['pages']))
                for key, value in result['query']['pages'].items():
                    if 'title' in value:
                        fields['page_name'] = value['title']
                    if 'missing' in value:
                        fields['found_content'] = False
                    if 'revisions' in value:
                        for rev in value['revisions']:
                            #print(str(rev))
                            fields['edit'] = {'flags': ''}
                            if 'timestamp' in rev:
                                fields['edit']['timestamp'] = rev['timestamp']
                            if 'user' in rev:
                                fields['edit']['user'] = rev['user']
                            if 'comment' in rev:
                                fields['edit']['comment'] = rev['comment']
                            if 'new' in rev:
                                fields['edit']['flags'] += 'N'
                            if 'minor' in rev:
                                fields['edit']['flags'] += 'm'
                            if '*' in rev:
                                fields = self.wikia_parse_content_page(rev['*'].replace('\r', ''), fields)
                                fields['found_content'] = True

        return fields['found_content'], fields
        #await ctx.send('The response was malformed:\r\n```json\r\n{}```'.format(result))
        #except Exception as ex:
        #    await ctx.send('Error: {}'.format(ex))

    async def wikia_api_get_category_members(self, wikia, page_name, limit = 10):
        """Gets the members of a category using the Wikia API."""
        page_name_quoted = urllib.parse.quote(page_name)
        url = 'action=query&list=categorymembers&cmtitle={}&cmlimit={}&format=json&redirects=1'.format(page_name_quoted, limit)
        result, base_url = await self.wikia_api_get(wikia, url)
        #print('category members json: ```{}```'.format(result))

        subcats = []
        members = []
        if not result is None and 'query' in result:
            if 'categorymembers' in result['query']:
                for member in result['query']['categorymembers']:
                    member_page_name = member['title']
                    ns = self.wikia_get_namespace(member_page_name)
                    if ns == 'Category':
                        subcats.append(member_page_name)
                    else:
                        members.append(member_page_name)
        return members, subcats

    async def wikia_api_get_image_info(self, wikia, page_name, thumb_width = None):
        """Gets the image info of an image using the Wikia API."""
        page_name_quoted = urllib.parse.quote(page_name)
        if thumb_width:
            iiurlwidth = '&iiurlwidth={}'.format(thumb_width)
        else:
            iiurlwidth = ''
        url = 'action=query&titles={}&prop=imageinfo&iiprop=timestamp|user|size|url{}&format=json&redirects=1'.format(page_name_quoted, iiurlwidth)
        result, base_url = await self.wikia_api_get(wikia, url)
        #print('image info json: ```{}```'.format(result))

        if not result is None and 'query' in result:
            if 'pages' in result['query']:
                #await ctx.send('```\r\n{}```'.format(result['query']['pages']))
                for key, value in result['query']['pages'].items():
                    if 'imageinfo' in value:
                        if len(value['imageinfo']) > 0:
                            #print(str(value['imageinfo'][0]))
                            return value['imageinfo'][0]

        return None

    async def wikia_api_get_image_serving_image(self, wikia, page_name):
        """Gets the image served for a page using the Wikia ImageServing API."""
        page_name_quoted = urllib.parse.quote(page_name)
        url = 'action=imageserving&wisTitle={}&format=json'.format(page_name_quoted)
        result, base_url = await self.wikia_api_get(wikia, url)
        #print('image info json: ```{}```'.format(result))

        if not result is None and 'image' in result:
            if 'imageserving' in result['image']:
                return result['image']['imageserving']

        return None

    def wikia_links(self, base_url, link_array, strip_ns = False):
        result = []
        for link in link_array:
            ns = self.wikia_get_namespace(link)
            dest = base_url + link
            if strip_ns and len(ns) > 0:
                link = link[len(ns) + 1:]
            result.append('[{}]({})'.format(link, dest.replace(' ', '_').replace(')', '\\)')))
        return self.cut(', '.join(result), 1000)

    def wikia_sort_category_members(self, members):
        buckets = {}
        for member in members:
            found = False
            for number in string.digits:
                if member[0] == number:
                    if not '#' in buckets:
                        buckets['#'] = []
                    buckets['#'].append(member)
                    found = True
            for letter in string.ascii_uppercase:
                if member[0].upper() == letter:
                    if not letter in buckets:
                        buckets[letter] = []
                    buckets[letter].append(member)
                    found = True
            if not found:
                if not '*' in buckets:
                    buckets['*'] = []
                buckets['*'].append(member)
        return buckets

    def wikia_embed_output(self, ctx, **kwargs):
        """Takes a set of returned fields from a combination of requests and returns the discord.Embed object to display."""
        wikia = kwargs['wikia']
        base_url = kwargs['base_url']
        title = kwargs['page_name']
        if not kwargs['section_name'] is None and len(kwargs['section_name']) > 0 and 'section_content' in kwargs:
            title = '{}{}'.format(kwargs['page_name'], kwargs['section_name_appender'])
        state = kwargs['search_state']
        if state == 'error_no_results':
            description = '*Error: Page not found and no title matches.*'
        elif state == 'error_multiple_choices':
            description = '*Error: Multiple search results.*'
        elif state == 'error_given_result_failed':
            description = '*Error: Search result returned this page, but it has no content. This page may be a "Special" listing.*'
        elif state == 'error_no_category':
            description = '*Error: Category not found and has no members.*'
        else:
            description = kwargs['page_content']

        #footer_fields = []

        # header section, title
        data = discord.Embed(
            title=title,
            url=kwargs['page_url'] + kwargs['section_url'],
            description=description,
            colour=discord.Colour(value=self.get_wikia_color(wikia)))

        # category results
        if 'cat_subcats' in kwargs:
            if len(kwargs['cat_subcats']) > 0:
                data.add_field(name="Sub-categories", value=self.wikia_links(base_url, kwargs['cat_subcats'], True), inline=False)
        if 'cat_members' in kwargs:
            if len(kwargs['cat_members']) > 10: # A-Z mode
                buckets = self.wikia_sort_category_members(kwargs['cat_members'])
                for bucket in sorted(buckets.keys()):
                    data.add_field(name=bucket, value=', '.join(buckets[bucket]), inline=False)
            elif len(kwargs['cat_members']) > 0: # link mode
                data.add_field(name="Members", value=self.wikia_links(base_url, kwargs['cat_members']), inline=False)
            else: # no members
                data.add_field(name="Members", value='*None*')

        # Section handling
        if not kwargs['section_name'] is None and len(kwargs['section_name']) > 0 and 'section_content' in kwargs:
            data.add_field(name=kwargs['section_name'], value=kwargs['section_content'], inline=False)
        if 'section_error' in kwargs:
            data.add_field(name='Section', value=kwargs['section_error'])
        #if 'links' in kwargs and len(kwargs['links']) > 0:
        #    for i in range(1, len(kwargs['links'])):
        #        print(str(i) + ' ' +str(kwargs['links'][i-1]))
        #if 'first_image' in kwargs:
            #if not kwargs['first_image'] is None:
                #print('FIRST_IMAGE = ' + kwargs['first_image'])

        # image dimensions and pre-last edit handling
        edit_detail = None
        if 'edit' in kwargs:
            edit_detail = kwargs['edit']
        if 'im_details' in kwargs and not kwargs['im_details'] is None:
            if not edit_detail:
                edit_detail = kwargs['im_details']
            #print('FI DETAILS')
            if 'thumburl' in kwargs['im_details']:
                # was 'first_image' in a page
                #print(kwargs['im_details']['url'])
                data.set_image(url=kwargs['im_details']['thumburl'])

            elif 'url' in kwargs['im_details']:
                # was a directly requested image
                #print(kwargs['im_details']['url'])
                data.set_image(url=kwargs['im_details']['url'])
                if 'size' in kwargs['im_details']:
                    w_h = ''
                    if 'width' in kwargs['im_details'] and 'height' in kwargs['im_details']:
                        w_h = ' | {}×{}'.format(kwargs['im_details']['width'], kwargs['im_details']['height'])
                    sz_i = kwargs['im_details']['size']
                    sz = '{:,d} bytes'.format(sz_i)
                    if sz_i > 1024:
                        sz_i = sz_i / 1024
                        sz = '{:,.1f} KB'.format(sz_i)
                        if sz_i > 1024:
                            sz_i = sz_i / 1024
                            sz = '{:,.1f} MB'.format(sz_i)
                    data.add_field(name='Size', value='{}{}'.format(sz, w_h))

        # last edit data
        if edit_detail:
            edit_t = ''
            edit_u = ''
            edit_f = ''
            edit_c = ''
            if  'timestamp' in edit_detail:
                edit_t = edit_detail['timestamp']
            if 'user' in edit_detail:
                edit_u = edit_detail['user']
            if 'flags' in edit_detail and len(edit_detail['flags']) > 0:
                edit_f = ' [{}] '.format(edit_detail['flags'])
            if 'comment' in edit_detail and len(edit_detail['comment']) > 0:
                edit_c_p, _ = self.wikia_parse_content_automata(edit_detail['comment'], kwargs['base_url'], no_link_urls=True)
                edit_c = ' ({})'.format(edit_c_p)
            edit = 'Last edited {} by {}{}{}'.format(edit_t, edit_u, edit_f, edit_c)
            data.add_field(name='Last edit', value=edit)
            #footer_fields.append(edit)

        # page categories
        if 'categories' in kwargs:
            if len(kwargs['categories']) > 0:
                data.add_field(name="Categories", value=self.wikia_links(base_url, kwargs['categories'], True))
            else:
                data.add_field(name="Categories", value='*Uncategorized*')

        # redirect result
        if 'redirected' in kwargs and not kwargs['redirected'] is None:
            data.add_field(name="Redirected from", value=kwargs['redirected'])

        # page search data
        if state == 'title':
            pass # was a direct match
        elif state == 'fuzzy' or state == 'error_given_result_failed':
            data.add_field(name='Search terms', value=kwargs['search_input'])
        elif state == 'error_multiple_choices':
            data.add_field(name='Search terms', value=kwargs['search_input'])
            data.add_field(name='Search results', value=self.wikia_links(base_url, kwargs['search_results']))

        # image caption
        if 'first_image_caption' in kwargs and len(kwargs['first_image_caption'].strip()) > 0:
            caption_p, _ = self.wikia_parse_content_automata(kwargs['first_image_caption'], kwargs['base_url'])
            data.add_field(name=self.cut('{}'.format(kwargs['first_image'][0].replace('_', ' ')), 25, 10), value=caption_p)
            #footer_fields.append('Image is "{}" with caption "{}"'.format(kwargs['first_image'][0].replace('_', ' '), caption_p))
        elif 'im_details' in kwargs and 'thumburl' in kwargs['im_details']:
            data.add_field(name=self.cut('{}'.format(kwargs['first_image'][0].replace('_', ' ')), 25, 10), value='*No caption provided.*')

        data.set_author(name='{} Wikia'.format(kwargs['wikia'].title()), url='{}Main_Page'.format(kwargs['base_url']))
        data.set_footer(text="Requested by {}".format(ctx.message.author))
        #print(data.to_dict())
        return data
    
    def normalize_section(self, sect):
        """Normalizes a section name."""
        return urllib.parse.unquote(sect.replace('_', ' ').replace('.', '%'))

    def wikia_link_is_image(self, link):
        link = link.strip()
        ns = self.wikia_get_namespace(link)
        #print(str(link) + '  ns = ' + str(ns) + '  endswith jpg?' + str(link.lower().endswith('.jpg')))
        if (ns == 'File' or ns == 'Image') and \
               (link.lower().endswith('.png') or \
                link.lower().endswith('.gif') or \
                link.lower().endswith('.jpg') or \
                link.lower().endswith('.jpeg')):
            return True
        else:
            return False

    def wikia_get_namespace(self, page_name):
        if page_name.find(':', 2) > 1:
            return page_name[:page_name.find(':', 2)]
        else:
            return ''

    def wikia_parse_link(self, page_content, start, end, bracket_depth):
        """Parses a link in a Wikia page into destination, text, and namespace."""
        if bracket_depth == 1:
            splitter = ' '
        elif bracket_depth == 2:
            splitter = '|'

        # [URL text here] or [[NAME|text here]] or [[NAME AND TEXT]]
        pos_s = start + bracket_depth
        pos_b = page_content.find(splitter, pos_s)
        pos_e = end - bracket_depth
        if pos_b < end and pos_b >= 0:
            dest = page_content[pos_s:pos_b].strip()
            text = page_content[pos_b + 1:pos_e].strip()
        else:
            dest = page_content[pos_s:pos_e].strip()
            text = dest
        dest = dest.replace(' ', '_')

        ext = 0
        if bracket_depth == 2:
            # additional stuff:
            # internal links get their "namespace" copied here (only special ones should be checked)
            ns = self.wikia_get_namespace(dest)
            # internal links get text-extending (until the first non-alphabetic character after the link-end).
            for char in page_content[end:]:
                if char.upper() in string.ascii_uppercase:
                    #print('append: {}'.format(char))
                    text += char
                    ext += 1
                else:
                    break
        else:
            ns = None

        return dest, text, ns, ext

    def cut(self, content, length, word_cut = 100):
        """Cuts off text after a given length, preferring a certain "word length"."""
        # loop after possible modification
        cut_point = 0
        prev_cut_point = 0
        pos = 0
        for char in content:
            # set "cut" points
            if char == ' ' or char == '\n' or char == '\t' or char == '-':
                cut_point = pos

            pos += 1

            # cut here; no more looping
            if cut_point > length:
                if prev_cut_point < length - word_cut:
                    content = content[:length - 3] + '...'
                else:
                    content = content[:prev_cut_point + 1] + '...'
                break
            else:
                prev_cut_point = cut_point
        return content

    def get_wikia_color(self, wikia):
        wikia = wikia.lower()
        if wikia == 'kiseki':
            return 0x005a73
        elif wikia == 'legendofheroes':
            return 0x6699ff
        elif wikia == 'trails':
            return 0x006cb0
        elif wikia == 'isu':
            return 0xdd360a
        elif wikia == 'megamitensei':
            return 0x721410
        elif wikia == 'onehundredpercentorangejuice':
            return 0xfe7e03
        else:
            return 0x000000

    def entity_replace(self, content):
        # replace wiki format with markdown format (by going to HTML)
        rwf_data = [
                {'find': "'''''", 'replace': '***'},
                {'find': "'''", 'replace': '**'},
                {'find': "''", 'replace': '*'},
                {'find': "&nbsp;", 'replace': ' '},
                {'find': "\u00A0", 'replace': ' '},
                {'find': "&quot;", 'replace': '"'},
                {'find': "&amp;", 'replace': '&'},
                {'find': "&lt;", 'replace': '<'},
                {'find': "&gt;", 'replace': '>'},
                ]
        for rwf in rwf_data:
            content = content.replace(rwf['find'], rwf['replace'])
        return content

    def wikia_parse_content_automata(self, page_content, base_url, *, no_link_urls=False):
        page_content = self.entity_replace(page_content)

        # parse links, templates, etc
        links = []

        page_content += ' '

        # llop for plain links
        pos = 0
        last_char = None
        for char in page_content:
            # find plain links (FOR DISCORD)
            if char == 'h' and last_char != '[':
                content_part = page_content[pos:]
                if content_part.lower().startswith('http://') or content_part.lower().startswith('https://'):
                    matchobj = find_whitespace.search(content_part)
                    if matchobj:
                        lookahead_endurl = matchobj.start()
                        page_content = page_content[:pos] + '<' + content_part[:lookahead_endurl] + '>' + content_part[lookahead_endurl:]
                    else:
                        page_content = page_content[:pos] + '<' + content_part + '>'
                    pos += 2

            last_char = char

            pos += 1

        # loop for link removal
        pos = 0
        templ_level = 0
        for char in page_content:
            if char == '{':
                templ_level += 1
            if char == '}' and templ_level > 0:
                templ_level -= 1
            if char == '.' and templ_level > 1:
                # make File:IMAGE.EXT into [[File:IMAGE.EXT]] and IMAGE.EXT into [[File:IMAGE.EXT]] within templates
                content_part = page_content[pos:]
                if content_part.lower().strip().startswith('.png') or \
                   content_part.lower().strip().startswith('.gif') or \
                   content_part.lower().strip().startswith('.jpg') or \
                   content_part.lower().strip().startswith('.jpeg'):
                    im_start0 = page_content.rfind('{', 0, pos) + 1
                    im_start1 = page_content.rfind('|', 0, pos) + 1
                    im_start2 = page_content.rfind('=', 0, pos) + 1
                    im_start3 = page_content.rfind('\n', 0, pos) + 1
                    im_start3 = page_content.rfind('>', 0, pos) + 1
                    im_start = max(im_start0, im_start1, im_start2, im_start3)
                    im_end = pos + 4
                    im = page_content[im_start:im_end].strip()
                    #print('image = ' + im)
                    if im.endswith('.jpe'):
                        im += 'g'
                        im_end += 1
                    if im.startswith('[[') and page_content[im_end:im_end + 2] == ']]':
                        im += ']]'
                        im_end += 2
                    if im.startswith('[[') and page_content[im_end:im_end + 1] == '|':
                        im += '|'
                        pos = im_end + 2
                        im_end0 = page_content.find('\n', pos)
                        im_end1 = page_content.find('<', pos)
                        im_end2 = page_content.find('}', pos)
                        if im_end0 > 0:
                            im_end = im_end0
                        if im_end1 > 0:
                            im_end = min(im_end, im_end1)
                        if im_end2 > 0:
                            im_end = min(im_end, im_end2)
                        im += page_content[pos:im_end]
                        im_end += 1
                    im = im.strip('[] ')
                    if len(im) > 0:
                        if not im.startswith('File:') and not im.startswith('Image:'):
                            im = '[[File:' + im + ']]'
                        else:
                            im = '[[' + im + ']]'
                        page_content = page_content[:im_start] + im + page_content[im_end:]
                        pos = im_start
            pos += 1

        pos = 0
        is_start_sqbr = False
        is_end_sqbr = False
        link_sqbr_depth = 0
        link_depth = 0
        link_start_pos = 0
        is_link_caption = False
        for char in page_content:
            # parse links
            if char == '[':
                if link_sqbr_depth >= 1 and not is_start_sqbr and not is_link_caption: # [ ] inside [ ]? stop parsing link
                    link_sqbr_depth = 0
                    link_depth = 0
                    #print(str(link_sqbr_depth))
                else:
                    link_sqbr_depth += 1
                    link_depth += 1
                    #print(str(link_sqbr_depth))
                    if not is_link_caption and is_start_sqbr: # set link pos
                        link_start_pos = pos - 1
                    is_start_sqbr = True
            else:
                if link_depth == 1 and is_start_sqbr:
                    link_start_pos = pos - 1
                is_start_sqbr = False

            if char == '|': # for File: links, the possibility of links in "caption-like" text arises
                if link_sqbr_depth == 2:
                    is_link_caption = True

            if char == ']':
                link_sqbr_depth -= 1
                #print(str(link_sqbr_depth))
                if link_sqbr_depth == 0:
                    if link_depth > 2:
                        link_depth = 2
                    link_end_pos = pos + 1
                    destination, text, namespace, link_extend_length = self.wikia_parse_link(page_content, link_start_pos, link_end_pos, link_depth)
                    if link_depth == 1 and not destination.startswith('http://') and not destination.startswith('https://') and not destination.startswith('//'):
                        # not a link! this may be a word enclosed in [ ].
                        #print('not a link: link={} text={} ns={} link_depth={} is_link_caption={}'.format(destination, text, namespace, link_depth, is_link_caption))
                        pass
                    else:
                        links.append((destination, text, namespace, link_start_pos, link_end_pos - link_start_pos))
                        #print('link: link={} text={} ns={} link_depth={}'.format(destination, text, namespace, link_depth))
                        if not namespace is None and (namespace == 'File' or namespace == 'Image' or namespace == 'Category' or len(namespace) == 2):
                            # remove File: (embedded images), Category: (category specs), XX: (other language page specs) - saved in links data
                            page_content = page_content[:link_start_pos] + page_content[link_end_pos + link_extend_length:]
                            pos = link_start_pos - 1
                        else:
                            if namespace == ':Category' or namespace == ':File' or namespace == ':Image':
                                # remove the ":" from the start
                                destination = destination[1:]
                                text = text[1:]
                            # prepend if not absolute URL
                            if not destination.startswith('http://') and not destination.startswith('https://') and not destination.startswith('//'):
                                destination = base_url + destination
                            if no_link_urls:
                                link_text = '[{}]'.format(text)
                            else:
                                link_text = '[{}]({})'.format(text, destination.replace(')', '\\)'))
                            page_content = '{}{}{}'.format(page_content[:link_start_pos], link_text, page_content[link_end_pos + link_extend_length:])
                            pos = link_start_pos + len(link_text) - 1
                    is_link_caption = False
                    link_depth = 0
                    pos -= link_extend_length
                    link_extend_length = 0
            else:
                is_end_sqbr = False
                link_found_end = False

            if char == '\n' and not is_link_caption:
                link_sqbr_depth = 0
                link_depth = 0

            pos += 1
            #char = page_content[pos]

        # loop for template removal
        pos = 0
        templ_level = 0
        templ_start_pos = 0
        is_start_brace = False
        is_end_brace = False
        is_pipe = False
        is_table = False
        for char in page_content:
            # skip tables and templates!
            if char == '|':
                if is_start_brace: # seq '{|'
                    is_table = True
                    if templ_level == 1:
                        templ_start_pos = pos - 1
                    is_start_brace = False
                is_pipe = True

            if char == '{':
                if is_start_brace: # seq '{{'
                    templ_level += 1
                    if templ_level == 1:
                        templ_start_pos = pos - 1
                    is_start_brace = False
                else:
                    is_start_brace = True
            else:
                is_start_brace = False
            
            if char == '}':
                if is_end_brace: # seq '}}'
                    templ_level -= 1
                    if templ_level == 0:
                        templ_end_pos = pos
                        page_content = page_content[:templ_start_pos] + page_content[templ_end_pos + 1:]
                        pos = templ_start_pos - 1
                    if templ_level < 0:
                        templ_level = 0
                    is_end_brace = False
                elif is_pipe and is_table: # seq '|}'
                    templ_level -= 1
                    if templ_level == 0:
                        templ_end_pos = pos
                        page_content = page_content[:templ_start_pos] + page_content[templ_end_pos + 1:]
                        pos = templ_start_pos - 1
                    if templ_level < 0:
                        templ_level = 0
                    is_table = False
                else:
                    is_end_brace = True
            else:
                is_end_brace = False

            if char != '|':
                is_pipe = False

            pos += 1

       ## strip html tags: format/keep content
       #sht_data = [
       #        {'tag': 'b', 'format': ['**','**']},
       #        {'tag': 'strong', 'format': ['**','**']},
       #        {'tag': 'i', 'format': ['*','*']},
       #        {'tag': 'em', 'format': ['*','*']},
       #        {'tag': 'u'},
       #        {'tag': 'p', 'format': ['\n', '']},
       #        {'tag': 'br', 'format': ['\n','']},
       #        {'tag': 'span'},
       #        {'tag': 'font'},
       #        {'tag': 'table', 'remove': True},
       #        {'tag': 'table', 'remove': True},
       #        {'tag': 'table', 'remove': True},
       #        {'tag': 'table', 'remove': True},
       #        {'tag': 'mainpage-leftcolumn-start', 'remove': True},
       #        {'tag': 'mainpage-rightcolumn-start', 'remove': True},
       #        {'tag': 'mainpage-endcolumn', 'remove': True},
       #        {'tag': 'rss', 'remove': True},
       #        ]

       #count = 0
       #pos = 0
       #for sht in sht_data:
       #    while '<' + sht['tag'] in page_content:
       #        tag_start_pos = page_content.find('<' + sht['tag'], pos)
       #        content_start_pos = page_content.find('>', tag_start_pos)
       #        if page_content[content_start_pos - 1] == '/': # self-closed
       #            content = ''
       #            tag_end_pos = content_start_pos
       #            tag_end_length = 1
       #        else:
       #            tag_end_pos = page_content.find('</' + sht['tag'] + '>', content_start_pos)
       #            tag_end_length = len(sht['tag']) + 3
       #            content = page_content[content_start_pos + 1:tag_end_pos]
       #        if 'remove' in sht and sht['remove']:
       #            content = ''
       #        if 'format' in sht:
       #            if len(sht['format']) > 0:
       #                content = sht['format'][0] + content
       #            if len(sht['format']) > 1:
       #                content = content + sht['format'][1]
       #        page_content = page_content[:tag_start_pos] + content + page_content[tag_end_pos + tag_end_length:]
       #        pos = tag_start_pos
       #        count += 1
       #        if count == 1000:a
       #            return page_content, None

        return page_content, links


    def wikia_parse_content_page(self, page_content, fields):
        """Parses the content of a Wikia page."""
        global find_whitespace

        page_content, links = self.wikia_parse_content_automata(page_content, fields['base_url'])

        # find header for section
        lines = page_content.split('\n')
        header_sect_content = ''
        sect_content = ''
        section_name = fields['section_name']
        current_section = None
        section_found = False
        for line in lines:
            # section header
            linet = line.strip()
            header_number = 0
            while len(linet) > 2 and linet[0] == '=' and linet[-1] == '=':
                linet = linet[1:-1]
                header_number += 1
                if header_number == 6:
                    break
            if header_number > 0:
                current_section = linet.strip(' ')
                if not section_name is None and self.normalize_section(current_section.lower()) == self.normalize_section(section_name.lower()):
                    section_found = True
                    section_name = current_section
                continue

            if current_section is None:
                header_sect_content += line + '\n'
            elif not section_name is None and not current_section is None and current_section == section_name:
                sect_content += line + '\n'

        fields['page_content'] = header_sect_content
        fields['page_content'] = self.cut(fields['page_content'], 2000)
        if not section_name is None and len(section_name) > 0:
            if section_found:
                fields['section_name']    = self.cut(section_name, 25, 10)
                fields['section_content'] = self.cut(sect_content, 1000)
            else:
                fields['section_name']  = None
                fields['section_name_appender'] = ''
                fields['section_url'] = ''
                fields['section_error'] = '*No section called "{}".*'.format(section_name)

        fields['links'] = links
        fields['categories'] = [x[0].replace('_', ' ') for x in links if x[2] == 'Category']
        fields['images'] = [(x[0], x[1]) for x in links if self.wikia_link_is_image(x[0])]
        #print(str(fields['images']))
        if len(fields['images']) > 0:
            fields['first_image'] = fields['images'][0]
            if len(fields['first_image'][1]) > 0:
                fic_parts = fields['first_image'][1].split('|')
                fic_result = ''
                options = True
                for part in fic_parts:
                    if options and match_file_options.match(part):
                        pass
                    else:
                        options = False
                        if len(fic_result) == 0:
                            fic_result = part
                        else:
                            fic_result += '|' + part
                fields['first_image_caption'] = fic_result
        else:
            fields['first_image'] = None

        return fields

    @commands.group()
    @checks.mod_or_permissions(manage_guild=True)
    async def wikiaset(self, ctx):
        """Wikia module settings."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help()
            return

    @wikiaset.command(name="default", aliases=["defaultwiki", "defaultwikia"])
    @checks.mod_or_permissions(manage_guild=True)
    async def wikiaset_default(self, ctx, subdomain):
        """Set the default Wikia for this server."""
        if ctx.guild is None:
            await ctx.send('*Error: You cannot set a default Wikia in private messages with me. Use the `wikiaset default` command in a server.*')
            return

        if subdomain.replace('_', '').isalnum() and len(subdomain) > 2:
            await self.config.guild(ctx.guild).default_wikia.set(subdomain)
            await ctx.send("The default Wikia for this server is now: <http://{}.wikia.com>".format(escape(subdomain)))
        else:
            await ctx.send("That Wikia subdomain is not valid.")


