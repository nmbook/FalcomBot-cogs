import discord
from redbot.core import commands, Config, checks
from redbot.core.utils.chat_formatting import escape, info, error
import aiohttp
import asyncio
import datetime
import os
import re
import string
import traceback
import urllib.parse

find_whitespace = re.compile("\\s")
match_file_options = re.compile("|".join(["border", "frameless", "frame", "thumb", "thumbnail",
                        "\d+px", "x\d+px", "\d+x\d+px", "upright",
                        "left", "right", "center", "none",
                        "baseline", "sub", "super", "top", "text-top", "middle", "bottom", "text-bottom",
                        "link=.*", "alt=.*", "page=.*", "class=.*", "lang=.*"]))

class Wikia(commands.Cog):
    """Command to view FANDOM Wiki pages."""

    def __init__(self, bot):
        default_guild = {
                "default_wikia": "",
                "accent_color_map": {},
                "tag_as_spoilers": False,
        }

        self.bot = bot
        self.config = Config.get_conf(self, identifier=0xff5269620002)
        self.config.register_guild(**default_guild)
        self.http_client = aiohttp.ClientSession()

    def cog_unload(self):
        self.bot.loop.create_task(self.http_client.close())

    __delete__ = cog_unload
    __unload = cog_unload

    @commands.command(aliases=["wikia"])
    async def fandom(self, ctx, *, search_terms : str):
        """FANDOM Wiki lookup. Finds a wiki page by name and displays it with formatting and images.
        
        Specify the wiki to use (if it's different from the default one set for this server) by typing "-w" followed by the wiki subdomain anywhere in the command.
        
        Alternatively, you may use a complete URL to an article to view the text and formatting on that page. Enclose it with <>s to avoid your own message generating a preview."""

        try:
            subdomain, page_name, section_name  = await self.parse_search_terms(ctx, search_terms)
            if subdomain is None:
                return

            fields = {}
            fields["search_state"] = "title"
            result, fields                  = await self.mw_api_get_page_content(subdomain, page_name, section_name, search_fields=fields)
            if not result and not fields["namespace"] in ["Category", "category"]:
                fields["search_state"] = "fuzzy"
                fields["search_input"] = page_name
                fields["search_results"], \
                  fields["search_warnings"] = await self.mw_api_search_pages(subdomain, page_name, "fuzzy", 10)

                #print(str(fields["search_results"]))
                if fields["search_results"] and len(fields["search_results"]) == 1:
                    result, fields          = await self.mw_api_get_page_content(subdomain, fields["search_results"][0], section_name, search_fields=fields)
                    if not result:
                        fields["search_state"] = "error_given_result_failed"
                elif fields["search_results"] and len(fields["search_results"]) > 1:
                    fields["search_state"] = "error_multiple_choices"
                else:
                    fields["search_state"] = "error_no_results"

            if result:
                if fields["namespace"] in ["File", "file", "Image", "image"]:
                    #print(page_name)
                    fields["im_details"]        = await self.mw_api_get_image_info(subdomain, page_name, thumb_width = None)
                elif "first_image" in fields and not fields["first_image"] is None:
                    #print(fields["first_image"][0])
                    fields["im_details"]        = await self.mw_api_get_image_info(subdomain, fields["first_image"][0], thumb_width = None)
                    #fields["im_serving"]        = await self.mw_api_get_image_serving_image(subdomain, page_name)

            if fields["namespace"] in ["Category", "category"]:
                fields["cat_members"], \
                      fields["cat_subcats"] = await self.mw_api_get_category_members(subdomain, page_name, 100)
                if len(fields["cat_members"]) == 0 and len(fields["cat_subcats"]) == 0 and not result:
                    fields["search_state"] = "error_no_category"
                    del fields["cat_members"]
                    del fields["cat_subcats"]

            content, embed = await self.mw_embed_output(ctx, **fields)

            try:
                await ctx.send(content=content, embed=embed)
            except Exception as ex:
                print("Exception on sending discord.Embed:\n{}\n".format(traceback.format_exc()))
                await ctx.send(escape("*Error: An error occurred sending the discord.Embed:* `{}`\nFalling back to legacy output.\n\n**__{}__{}** (<{}{}>):\n\n{}".format(
                            str(ex),
                            fields["page_name"], 
                            fields["section_name_appender"],
                            fields["page_url"], 
                            fields["section_url"],
                            fields["page_content"]), mass_mentions = True))
        except Exception as ex:
            print("Exception in [p]wiki command:\n{}\n".format(traceback.format_exc()))
            await ctx.send(escape(error("An error occurred processing the FANDOM Wiki API: `{}`".format(ex)), mass_mentions = True))


    async def parse_search_terms(self, ctx, search_terms):
        """Parses the search terms into "subdomain", "page_name", and "section_name" parts."""
        search_terms = search_terms.strip(" <>:\t\n")
        if search_terms.lower().startswith("http://") or search_terms.lower().startswith("https://") or search_terms.startswith("//"):
            subd_start = search_terms.find("/") + 2
            subd_end = search_terms.find(".", subd_start)
            search_start = search_terms.find("/", subd_start) + 1
        elif search_terms.lower().startswith("-w ") or search_terms.lower().startswith("-wiki "):
            subd_start = search_terms.find(" ") + 1
            subd_end = search_terms.find(" ", subd_start)
            search_start = subd_end + 1
        else:
            subd_start = -1
            subd_end = -1
            search_start = 0

        if subd_end >= 0 and subd_start >= 0:
            subdomain = search_terms[subd_start:subd_end]
            search_terms = search_terms[search_start:].strip(" <>:\t\n")
            if search_terms.startswith("wiki/") or search_terms.startswith("w/"):
                search_start = search_terms.find("/") + 1
                search_terms = search_terms[search_start:].strip(" <>:\t\n")
            if not self.util_subdomain_is_valid(subdomain):
                await ctx.send(error("That subdomain is not valid."))
                return None, None, None
        else:
            if ctx.guild is None:
                await ctx.send(error("Because you cannot set a default wiki in private messages with me, you must use this command with a `-w`/`-wiki` parameter that specifies the wiki to use."))
                return None, None, None

            subdomain = await self.config.guild(ctx.guild).default_wikia()
            if subdomain is None or not self.util_subdomain_is_valid(subdomain):
                await ctx.send(error("No default wiki has been set for this server. You must use this command with a `-w`/`-wiki` parameter that specifies the wiki to use.*"))
                return None, None, None

        if "#" in search_terms:
            parts = search_terms.split("#", 1)
            search_terms = parts[0].strip(" <>:\t\n")
            section = parts[1].strip(" <>:\t\n")
            section = self.mw_normalize_section(section.replace("_", " "))
        else:
            search_terms = search_terms.strip()
            section = None

        search_terms = search_terms.replace("_", " ")
        return subdomain, search_terms, section

    async def mw_api_get(self, subdomain, api_url):
        """Performs a FANDOM Wiki API request."""
        base_url = "https://{}.fandom.com/wiki/".format(subdomain)
        base_api_url = "https://{}.fandom.com/api.php?".format(subdomain)
        url = "{}{}".format(base_api_url, api_url)
        headers = {"User-Agent": "WikiReaderCog/1.1 RedDiscordBot/3.0 DiscordPy/1.0"}
        result = None
        async with self.http_client.get(url, headers=headers) as r:
            result = await r.json()
        return result, base_url

    async def mw_api_search_pages(self, subdomain, page_name, profile = "fuzzy", limit = 10):
        """Searches for a page by title using the FANDOM Wiki API."""
        page_name_quoted = urllib.parse.quote(page_name)
        url = "action=opensearch&search={}&namespace=&profile={}&redirects=resolve&limit={}&format=json".format(page_name_quoted, profile, limit)
        result, base_url = await self.mw_api_get(subdomain, url)
        #print("search json: ```{}```".format(result))

        warnings = None
        if "warnings" in result:
            if "opensearch" in result["warnings"]:
                warnings = str(result["warnings"]["opensearch"])

        if isinstance(result, list):
            return result[1], warnings
        elif "1" in result:
            return result["1"], warnings
        else:
            return [], warnings

    async def mw_api_get_page_images(self, subdomain, page_name, limit = 1):
        """Gets the pageimages of a page using the FANDOM Wiki API.
        
        This wasn't working as intended so is currently unused!"""
        page_name_quoted = urllib.parse.quote(page_name)
        url = "action=query&prop=images&titles={}&imlimit={}&format=json".format(page_name_quoted, limit)
        result, base_url = await self.mw_api_get(subdomain, url)
        #print("pageimages json: ```{}```".format(result))

        if not result is None and "query" in result:
            if "pages" in result["query"]:
                #await ctx.send("```\r\n{}```".format(result["query"]["pages"]))
                for key, value in result["query"]["pages"].items():
                    if "images" in value:
                        for img in value["images"]:
                            if "title" in img:
                                #print(img["title"])
                                pass
        return []

    async def mw_api_get_page_content(self, subdomain, page_name, section_name, search_fields = {}):
        """Gets the content of a page using the FANDOM Wiki API."""
        page_name_quoted = urllib.parse.quote(page_name)
        url = "action=query&titles={}&prop=revisions&rvprop=timestamp|flags|comment|user|size|content&format=json&redirects=1".format(page_name_quoted)
        result, base_url = await self.mw_api_get(subdomain, url)

        fields = search_fields
        fields["found_content"] = False
        fields["subdomain"] = subdomain
        fields["base_url"] = base_url
        fields["page_name"] = page_name
        fields["namespace"] = self.mw_get_namespace(page_name)
        fields["page_url"] = base_url + urllib.parse.quote(page_name.replace(" ", "_"))
        fields["section_name"] = section_name
        fields["page_content"] = ""
        if section_name and len(section_name) > 0:
            fields["section_name_appender"] = " \u2192 {}".format(section_name)
            fields["section_url"] = "#{}".format(urllib.parse.quote(section_name.replace(" ", "_")).replace("%", "."))
        else:
            fields["section_name_appender"] = ""
            fields["section_url"] = ""
        
        if not result is None and "query" in result:
            fields["redirected"] = None
            if "normalized" in result["query"]:
                if len(result["query"]["normalized"]) > 0:
                    if "to" in result["query"]["normalized"][0]:
                        fields["page_name"] = result["query"]["normalized"][0]["to"]
            if "redirects" in result["query"]:
                if len(result["query"]["redirects"]) > 0:
                    if "from" in result["query"]["redirects"][0]:
                        fields["redirected"] = result["query"]["redirects"][0]["from"]
                    if "to" in result["query"]["redirects"][0]:
                        fields["page_name"] = result["query"]["redirects"][0]["to"]
            if "pages" in result["query"]:
                #await ctx.send("```\r\n{}```".format(result["query"]["pages"]))
                for key, value in result["query"]["pages"].items():
                    if "title" in value:
                        fields["page_name"] = value["title"]
                    if "missing" in value:
                        fields["found_content"] = False
                    if "revisions" in value:
                        for rev in value["revisions"]:
                            #print(str(rev))
                            fields["edit"] = {"flags": ""}
                            if "timestamp" in rev:
                                fields["edit"]["timestamp"] = rev["timestamp"]
                            if "user" in rev:
                                fields["edit"]["user"] = rev["user"]
                            if "comment" in rev:
                                fields["edit"]["comment"] = rev["comment"]
                            if "new" in rev:
                                fields["edit"]["flags"] += "N"
                            if "minor" in rev:
                                fields["edit"]["flags"] += "m"
                            if "*" in rev:
                                fields = self.mw_parse_content_page(rev["*"].replace("\r", ""), fields)
                                fields["found_content"] = True

        return fields["found_content"], fields
        #await ctx.send("The response was malformed:\r\n```json\r\n{}```".format(result))
        #except Exception as ex:
        #    await ctx.send("Error: {}".format(ex))

    async def mw_api_get_category_members(self, subdomain, page_name, limit = 10):
        """Gets the members of a category using the FANDOM Wiki API."""
        page_name_quoted = urllib.parse.quote(page_name)
        url = "action=query&list=categorymembers&cmtitle={}&cmlimit={}&format=json&redirects=1".format(page_name_quoted, limit)
        result, base_url = await self.mw_api_get(subdomain, url)
        #print("category members json: ```{}```".format(result))

        subcats = []
        members = []
        if not result is None and "query" in result:
            if "categorymembers" in result["query"]:
                for member in result["query"]["categorymembers"]:
                    member_page_name = member["title"]
                    ns = self.mw_get_namespace(member_page_name)
                    if ns in ["Category", "category"]:
                        subcats.append(member_page_name)
                    else:
                        members.append(member_page_name)
        return members, subcats

    async def mw_api_get_image_info(self, subdomain, page_name, thumb_width = None):
        """Gets the image info of an image using the FANDOM Wiki API."""
        page_name_quoted = urllib.parse.quote(page_name)
        if thumb_width:
            iiurlwidth = "&iiurlwidth={}".format(thumb_width)
        else:
            iiurlwidth = ""
        url = "action=query&titles={}&prop=imageinfo&iiprop=timestamp|user|size|url{}&format=json&redirects=1".format(page_name_quoted, iiurlwidth)
        result, base_url = await self.mw_api_get(subdomain, url)
        #print("image info json: ```{}```".format(result))

        if not result is None and "query" in result:
            if "pages" in result["query"]:
                #await ctx.send("```\r\n{}```".format(result["query"]["pages"]))
                for key, value in result["query"]["pages"].items():
                    if "imageinfo" in value:
                        if len(value["imageinfo"]) > 0:
                            #print(str(value["imageinfo"][0]))
                            return value["imageinfo"][0]

        return None

    async def mw_api_get_image_serving_image(self, subdomain, page_name):
        """Gets the image served for a page using the Wikia ImageServing API."""
        page_name_quoted = urllib.parse.quote(page_name)
        url = "action=imageserving&wisTitle={}&format=json".format(page_name_quoted)
        result, base_url = await self.mw_api_get(subdomain, url)
        #print("image info json: ```{}```".format(result))

        if not result is None and "image" in result:
            if "imageserving" in result["image"]:
                return result["image"]["imageserving"]

        return None

    def mw_format_links(self, base_url, link_array, strip_ns = False):
        """Convert the list of links into a list of formatted [TEXT](URL) strings."""
        result = []
        for link in link_array:
            ns = self.mw_get_namespace(link)
            dest = base_url + link
            if strip_ns and len(ns) > 0:
                link = link[len(ns) + 1:]
            result.append("[{}]({})".format(link, dest.replace(" ", "_").replace(")", "\\)")))
        return self.util_string_cut(", ".join(result), 1024)

    def mw_sort_category_members(self, members):
        """Sort categories into alphabetical buckets like wikis do."""
        buckets = {}
        for member in members:
            found = False
            for number in string.digits:
                if member[0] == number:
                    if not "#" in buckets:
                        buckets["#"] = []
                    buckets["#"].append(member)
                    found = True
            for letter in string.ascii_uppercase:
                if member[0].upper() == letter:
                    if not letter in buckets:
                        buckets[letter] = []
                    buckets[letter].append(member)
                    found = True
            if not found:
                if not "*" in buckets:
                    buckets["*"] = []
                buckets["*"].append(member)
        return buckets

    async def mw_embed_output(self, ctx, **kwargs):
        """Takes a set of returned fields from a combination of requests and returns the discord.Embed object to display."""
        subdomain = kwargs["subdomain"]
        base_url = kwargs["base_url"]
        title = kwargs["page_name"]
        if not kwargs["section_name"] is None and len(kwargs["section_name"]) > 0 and "section_content" in kwargs:
            title = "{}{}".format(kwargs["page_name"], kwargs["section_name_appender"])
        state = kwargs["search_state"]
        if state == "error_no_results":
            description = "*Error: Page not found and no title matches.*"
        elif state == "error_multiple_choices":
            description = "*Error: Multiple search results.*"
        elif state == "error_given_result_failed":
            description = "*Error: Search result returned this page, but it has no content. This page may be a Special: listing.*"
        elif state == "error_no_category":
            description = "*Error: Category not found and has no members.*"
        else:
            description = kwargs["page_content"]

        #footer_fields = []

        # header section, title
        data = discord.Embed(
            title=title,
            url=kwargs["page_url"] + kwargs["section_url"],
            description=description)

        color_o = None
        async with self.config.guild(ctx.guild).accent_color_map() as colors:
            if subdomain in colors:
                color_o = discord.Color(value=colors[subdomain])
        if color_o:
            data.color = color_o

        data.set_author(name="{} Wiki".format(kwargs["subdomain"].title()), url="{}Main_Page".format(kwargs["base_url"]))

        content = ""
        if not state.startswith("error") and await self.config.guild(ctx.guild).tag_as_spoilers():
            content = "**{wiki_name} result** (URL: ||{url}||)".format(wiki_name=data.author.name, title=data.title, url=data.url)

        # category results
        if "cat_subcats" in kwargs:
            if len(kwargs["cat_subcats"]) > 0:
                data.add_field(name="Sub-categories", value=self.mw_format_links(base_url, kwargs["cat_subcats"], True), inline=False)
        if "cat_members" in kwargs:
            if len(kwargs["cat_members"]) > 10: # A-Z mode
                buckets = self.mw_sort_category_members(kwargs["cat_members"])
                for bucket in sorted(buckets.keys()):
                    data.add_field(name=bucket, value=", ".join(buckets[bucket]), inline=False)
            elif len(kwargs["cat_members"]) > 0: # link mode
                data.add_field(name="Members", value=self.mw_format_links(base_url, kwargs["cat_members"]), inline=False)
            else: # no members
                data.add_field(name="Members", value="*None*")

        # Section handling
        if not kwargs["section_name"] is None and len(kwargs["section_name"]) > 0 and "section_content" in kwargs:
            if len(kwargs["section_content"]) > 0:
                data.add_field(name=kwargs["section_name"], value=kwargs["section_content"], inline=False)
            else:
                data.add_field(name=kwargs["section_name"], value="*This section is empty.*", inline=False)
        if "section_error" in kwargs and len(kwargs["section_error"]) > 0:
            data.add_field(name="Section", value=kwargs["section_error"])
        #if "links" in kwargs and len(kwargs["links"]) > 0:
        #    for i in range(1, len(kwargs["links"])):
        #        print(str(i) + " " +str(kwargs["links"][i-1]))
        #if "first_image" in kwargs:
            #if not kwargs["first_image"] is None:
                #print("FIRST_IMAGE = " + kwargs["first_image"])

        # image dimensions and pre-last edit handling
        edit_detail = None
        if "edit" in kwargs:
            edit_detail = kwargs["edit"]
        if "im_details" in kwargs and not kwargs["im_details"] is None:
            if not edit_detail:
                edit_detail = kwargs["im_details"]
            #print("FI DETAILS")
            if "thumburl" in kwargs["im_details"]:
                # was "first_image" in a page
                #print(kwargs["im_details"]["url"])
                data.set_image(url=kwargs["im_details"]["thumburl"])

            elif "url" in kwargs["im_details"]:
                # was a directly requested image
                #print(kwargs["im_details"]["url"])
                data.set_image(url=kwargs["im_details"]["url"])
                if not ("first_image" in kwargs and not kwargs["first_image"] is None) and "size" in kwargs["im_details"] and not kwargs["im_details"]["size"] is None:
                    sz, w, h = kwargs["im_details"]["size"], None, None
                    if "width" in kwargs["im_details"] and "height" in kwargs["im_details"]:
                        w, h = kwargs["im_details"]["width"], kwargs["im_details"]["height"]

                    data.add_field(name="Size", value=self.util_size_to_string(sz, w, h))

        # last edit data
        footer_edit_time = None
        footer_edit_text = None
        if edit_detail:
            edit_t = ""
            edit_u = ""
            edit_f = ""
            edit_c = ""
            if  "timestamp" in edit_detail:
                edit_t = edit_detail["timestamp"]
                try:
                    footer_edit_time = datetime.datetime.strptime(edit_t, "%Y-%m-%dT%H:%M:%S%z")
                except ValueError:
                    # don't save anything
                    pass
            if "user" in edit_detail:
                edit_u = edit_detail["user"]
            if "flags" in edit_detail and len(edit_detail["flags"]) > 0:
                edit_f = " [{}] ".format(edit_detail["flags"])
            if "comment" in edit_detail and len(edit_detail["comment"]) > 0:
                edit_c_p, _ = self.mw_parse_content_automata(edit_detail["comment"], kwargs["base_url"], no_link_urls=True)
                edit_c = " ({})".format(edit_c_p.strip())
            edit = "Last edited {} by {}{}{}".format(edit_t, edit_u, edit_f, edit_c)
            #data.add_field(name="Last edit", value=edit)
            footer_edit_text = "Last edited by {}{}{}.".format(edit_u, edit_f, edit_c)

        # page categories
        if "categories" in kwargs:
            if len(kwargs["categories"]) > 0:
                data.add_field(name="Categories", value=self.mw_format_links(base_url, kwargs["categories"], True))
            else:
                data.add_field(name="Categories", value="*Uncategorized*")

        # redirect result
        if "redirected" in kwargs and not kwargs["redirected"] is None:
            data.add_field(name="Redirected from", value=kwargs["redirected"])

        # page search data
        if state == "title":
            pass # was a direct match
        elif state == "fuzzy" or state == "error_given_result_failed":
            data.add_field(name="Search terms", value=kwargs["search_input"])
        elif state == "error_multiple_choices":
            data.add_field(name="Search terms", value=kwargs["search_input"])
            data.add_field(name="Search results", value=self.mw_format_links(base_url, kwargs["search_results"]))

        # image caption
        if "first_image_caption" in kwargs and len(kwargs["first_image_caption"].strip()) > 0:
            caption_p, _ = self.mw_parse_content_automata(kwargs["first_image_caption"], kwargs["base_url"])
            data.add_field(name=self.util_string_cut("{}".format(kwargs["first_image"][0].replace("_", " ")), 256, 10), value=self.util_string_cut(caption_p, 1024, 10))
            #footer_fields.append("Image is "{}" with caption "{}"".format(kwargs["first_image"][0].replace("_", " "), caption_p))
        elif "first_image" in kwargs and not kwargs["first_image"] is None:
            data.add_field(name=self.util_string_cut("{}".format(kwargs["first_image"][0].replace("_", " ")), 256, 10), value="*No caption provided.*")

        #data.set_footer(text="Requested by {}".format(ctx.message.author))
        #data.timestamp = datetime.datetime.utcnow()
        if footer_edit_text:
            data.set_footer(text=footer_edit_text)
        if footer_edit_time:
            data.timestamp = footer_edit_time
        #print(data.to_dict())

        return content, data
    
    def mw_normalize_section(self, sect):
        """Normalizes a section name."""
        return urllib.parse.unquote(sect.replace("_", " ").replace(".", "%"))

    def mw_is_link_image(self, link):
        link = link.strip()
        ns = self.mw_get_namespace(link)
        #print(str(link) + "  ns = " + str(ns) + "  endswith jpg?" + str(link.lower().endswith(".jpg")))
        if ns in ["File", "file", "Image", "image"] and \
               (link.lower().endswith(".png") or \
                link.lower().endswith(".gif") or \
                link.lower().endswith(".jpg") or \
                link.lower().endswith(".jpeg")):
            return True
        else:
            return False

    def mw_get_namespace(self, page_name):
        """Retrieve the namespace of a link."""
        if page_name.find(":", 2) > 1:
            return page_name[:page_name.find(":", 2)]
        else:
            return ""

    def mw_parse_link(self, page_content, start, end, bracket_depth):
        """Parses a link in a wiki page into destination, text, and namespace."""
        if bracket_depth == 1:
            splitter = " "
        elif bracket_depth == 2:
            splitter = "|"

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
        dest = dest.replace(" ", "_")

        ext = 0
        if bracket_depth == 2:
            # additional stuff:
            # internal links get their "namespace" copied here (only special ones should be checked)
            ns = self.mw_get_namespace(dest)
            # internal links get text-extending (until the first non-alphabetic character after the link-end).
            for char in page_content[end:]:
                if char.upper() in string.ascii_uppercase:
                    #print("append: {}".format(char))
                    text += char
                    ext += 1
                else:
                    break
        else:
            ns = None

        return dest, text, ns, ext

    def mw_entity_replace(self, content):
        """Replace wiki format for simple styles with the equivalent Markdown."""
        rwf_data = [
                {"find": "'''''", "replace": "***"},
                {"find": "'''", "replace": "**"},
                {"find": "''", "replace": "*"},
                {"find": "&nbsp;", "replace": " "},
                {"find": "\u00A0", "replace": " "},
                {"find": "&quot;", "replace": "\""},
                {"find": "&amp;", "replace": "&"},
                {"find": "&lt;", "replace": "<"},
                {"find": "&gt;", "replace": ">"},
                ]
        for rwf in rwf_data:
            content = content.replace(rwf["find"], rwf["replace"])
        return content

    def mw_parse_content_automata(self, page_content, base_url, *, no_link_urls=False):
        """Parse wiki content by finding complex formatting objects and generating links lists, stripping templates, and other related tasks.

        Don't look at this function, it's ugly."""
        page_content = self.mw_entity_replace(page_content)

        # parse links, templates, etc
        links = []

        page_content += " "

        # llop for plain links
        pos = 0
        last_char = None
        for char in page_content:
            # find plain links (FOR DISCORD)
            if char == "h" and last_char != "[":
                content_part = page_content[pos:]
                if content_part.lower().startswith("http://") or content_part.lower().startswith("https://"):
                    matchobj = find_whitespace.search(content_part)
                    if matchobj:
                        lookahead_endurl = matchobj.start()
                        page_content = page_content[:pos] + "<" + content_part[:lookahead_endurl] + ">" + content_part[lookahead_endurl:]
                    else:
                        page_content = page_content[:pos] + "<" + content_part + ">"
                    pos += 2

            last_char = char

            pos += 1

        # loop for link removal
        pos = 0
        templ_level = 0
        for char in page_content:
            if char == "{":
                templ_level += 1
            if char == "}" and templ_level > 0:
                templ_level -= 1
            if char == "." and templ_level > 1:
                # make File:IMAGE.EXT into [[File:IMAGE.EXT]] and IMAGE.EXT into [[File:IMAGE.EXT]] within templates
                content_part = page_content[pos:]
                if content_part.lower().strip().startswith(".png") or \
                   content_part.lower().strip().startswith(".gif") or \
                   content_part.lower().strip().startswith(".jpg") or \
                   content_part.lower().strip().startswith(".jpeg"):
                    im_start0 = page_content.rfind("{", 0, pos) + 1
                    im_start1 = page_content.rfind("|", 0, pos) + 1
                    im_start2 = page_content.rfind("=", 0, pos) + 1
                    im_start3 = page_content.rfind("\n", 0, pos) + 1
                    im_start3 = page_content.rfind(">", 0, pos) + 1
                    im_start = max(im_start0, im_start1, im_start2, im_start3)
                    im_end = pos + 4
                    im = page_content[im_start:im_end].strip()
                    #print("image = " + im)
                    if im.endswith(".jpe"):
                        im += "g"
                        im_end += 1
                    if im.startswith("[[") and page_content[im_end:im_end + 2] == "]]":
                        im += "]]"
                        im_end += 2
                    if im.startswith("[[") and page_content[im_end:im_end + 1] == "|":
                        im += "|"
                        pos = im_end + 2
                        im_end0 = page_content.find("\n", pos)
                        im_end1 = page_content.find("<", pos)
                        im_end2 = page_content.find("}", pos)
                        if im_end0 > 0:
                            im_end = im_end0
                        if im_end1 > 0:
                            im_end = min(im_end, im_end1)
                        if im_end2 > 0:
                            im_end = min(im_end, im_end2)
                        im += page_content[pos:im_end]
                        im_end += 1
                    im = im.strip("[] ")
                    if len(im) > 0:
                        if not im.startswith("File:") and not im.startswith("Image:") and not im.startswith("file:") and not im.startswith("image:"):
                            im = "[[File:" + im + "]]"
                        else:
                            im = "[[" + im + "]]"
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
            if char == "[":
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

            if char == "|": # for File: links, the possibility of links in "caption-like" text arises
                if link_sqbr_depth == 2:
                    is_link_caption = True

            if char == "]":
                link_sqbr_depth -= 1
                #print(str(link_sqbr_depth))
                if link_sqbr_depth == 0:
                    if link_depth > 2:
                        link_depth = 2
                    link_end_pos = pos + 1
                    destination, text, namespace, link_extend_length = self.mw_parse_link(page_content, link_start_pos, link_end_pos, link_depth)
                    if link_depth == 1 and not destination.startswith("http://") and not destination.startswith("https://") and not destination.startswith("//"):
                        # not a link! this may be a word enclosed in [ ].
                        #print("not a link: link={} text={} ns={} link_depth={} is_link_caption={}".format(destination, text, namespace, link_depth, is_link_caption))
                        pass
                    else:
                        links.append((destination, text, namespace, link_start_pos, link_end_pos - link_start_pos))
                        #print("link: link={} text={} ns={} link_depth={}".format(destination, text, namespace, link_depth))
                        if not namespace is None and (namespace in ["File", "file", "Image", "image", "Category", "category"] or len(namespace) == 2):
                            # remove File: (embedded images), Category: (category specs), XX: (other language page specs) - saved in links data
                            page_content = page_content[:link_start_pos] + page_content[link_end_pos + link_extend_length:]
                            pos = link_start_pos - 1
                        else:
                            if namespace in [":Category", ":category", ":File", ":file", ":Image", ":image"]:
                                # remove the ":" from the start
                                if text.startswith(destination):
                                    text = text[1:]
                                destination = destination[1:]
                            # prepend if not absolute URL
                            if not destination.startswith("http://") and not destination.startswith("https://") and not destination.startswith("//"):
                                destination = base_url + destination
                            if no_link_urls:
                                link_text = "[{}]".format(text)
                            else:
                                link_text = "[{}]({})".format(text, destination.replace(")", "\\)"))
                            page_content = "{}{}{}".format(page_content[:link_start_pos], link_text, page_content[link_end_pos + link_extend_length:])
                            pos = link_start_pos + len(link_text) - 1
                    is_link_caption = False
                    link_depth = 0
                    pos -= link_extend_length
                    link_extend_length = 0
            else:
                is_end_sqbr = False
                link_found_end = False

            if char == "\n" and not is_link_caption:
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
            if char == "|":
                if is_start_brace: # seq "{|"
                    is_table = True
                    if templ_level == 1:
                        templ_start_pos = pos - 1
                    is_start_brace = False
                is_pipe = True

            if char == "{":
                if is_start_brace: # seq "{{"
                    templ_level += 1
                    if templ_level == 1:
                        templ_start_pos = pos - 1
                    is_start_brace = False
                else:
                    is_start_brace = True
            else:
                is_start_brace = False
            
            if char == "}":
                if is_end_brace: # seq "}}"
                    templ_level -= 1
                    if templ_level == 0:
                        templ_end_pos = pos
                        page_content = page_content[:templ_start_pos] + page_content[templ_end_pos + 1:]
                        pos = templ_start_pos - 1
                    if templ_level < 0:
                        templ_level = 0
                    is_end_brace = False
                elif is_pipe and is_table: # seq "|}"
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

            if char != "|":
                is_pipe = False

            pos += 1

       ## strip html tags: format/keep content
       #sht_data = [
       #        {"tag": "b", "format": ["**","**"]},
       #        {"tag": "strong", "format": ["**","**"]},
       #        {"tag": "i", "format": ["*","*"]},
       #        {"tag": "em", "format": ["*","*"]},
       #        {"tag": "u"},
       #        {"tag": "p", "format": ["\n", ""]},
       #        {"tag": "br", "format": ["\n",""]},
       #        {"tag": "span"},
       #        {"tag": "font"},
       #        {"tag": "table", "remove": True},
       #        {"tag": "table", "remove": True},
       #        {"tag": "table", "remove": True},
       #        {"tag": "table", "remove": True},
       #        {"tag": "mainpage-leftcolumn-start", "remove": True},
       #        {"tag": "mainpage-rightcolumn-start", "remove": True},
       #        {"tag": "mainpage-endcolumn", "remove": True},
       #        {"tag": "rss", "remove": True},
       #        ]

       #count = 0
       #pos = 0
       #for sht in sht_data:
       #    while "<" + sht["tag"] in page_content:
       #        tag_start_pos = page_content.find("<" + sht["tag"], pos)
       #        content_start_pos = page_content.find(">", tag_start_pos)
       #        if page_content[content_start_pos - 1] == "/": # self-closed
       #            content = ""
       #            tag_end_pos = content_start_pos
       #            tag_end_length = 1
       #        else:
       #            tag_end_pos = page_content.find("</" + sht["tag"] + ">", content_start_pos)
       #            tag_end_length = len(sht["tag"]) + 3
       #            content = page_content[content_start_pos + 1:tag_end_pos]
       #        if "remove" in sht and sht["remove"]:
       #            content = ""
       #        if "format" in sht:
       #            if len(sht["format"]) > 0:
       #                content = sht["format"][0] + content
       #            if len(sht["format"]) > 1:
       #                content = content + sht["format"][1]
       #        page_content = page_content[:tag_start_pos] + content + page_content[tag_end_pos + tag_end_length:]
       #        pos = tag_start_pos
       #        count += 1
       #        if count == 1000:a
       #            return page_content, None

        return page_content, links


    def mw_parse_content_page(self, page_content, fields):
        """Parses the content of a wiki page."""
        global find_whitespace

        page_content, links = self.mw_parse_content_automata(page_content, fields["base_url"])

        # find header for section
        lines = page_content.split("\n")
        header_sect_content = ""
        sect_content = ""
        section_name = fields["section_name"]
        current_section = None
        section_found = False
        for line in lines:
            # section header
            linet = line.strip()
            header_number = 0
            while len(linet) > 2 and linet[0] == "=" and linet[-1] == "=":
                linet = linet[1:-1]
                header_number += 1
                if header_number == 6:
                    break
            if header_number > 0:
                current_section = linet.strip(" ")
                if not section_name is None and self.mw_normalize_section(current_section.lower()) == self.mw_normalize_section(section_name.lower()):
                    section_found = True
                    section_name = current_section
                continue

            if current_section is None:
                header_sect_content += line + "\n"
            elif not section_name is None and not current_section is None and current_section == section_name:
                sect_content += line + "\n"

        fields["page_content"] = header_sect_content
        fields["page_content"] = self.util_string_cut(fields["page_content"], 2048)
        if not section_name is None and len(section_name) > 0:
            if section_found:
                fields["section_name"]    = self.util_string_cut(section_name, 256, 10)
                fields["section_content"] = self.util_string_cut(sect_content, 1024)
            else:
                fields["section_name"]  = None
                fields["section_name_appender"] = ""
                fields["section_url"] = ""
                fields["section_error"] = "*Error: No section called `{}`.*".format(section_name)

        fields["links"] = links
        fields["categories"] = [x[0].replace("_", " ") for x in links if x[2] in ["Category", "category"]]
        fields["images"] = [(x[0], x[1]) for x in links if self.mw_is_link_image(x[0])]
        #print(str(fields["images"]))
        if len(fields["images"]) > 0:
            fields["first_image"] = fields["images"][0]
            if len(fields["first_image"][1]) > 0:
                fic_parts = fields["first_image"][1].split("|")
                fic_result = ""
                options = True
                for part in fic_parts[1:]:
                    if options and match_file_options.match(part):
                        pass
                    else:
                        options = False
                        if len(fic_result) == 0:
                            fic_result = part
                        else:
                            fic_result += "|" + part
                fields["first_image_caption"] = fic_result
        else:
            fields["first_image"] = None

        return fields

    def util_size_to_string(self, sz, w, h):
        """Return a human-readable byte, width, and height size value on the given (bytes, width, height) input."""
        str_sz = ""
        if sz:
            int_sz = sz
            sz_mags = ["bytes", "KB", "MB", "GB", "TB"]
            sz_mag = 0
            sz_fmt = "{:,d}"
            while True:
                str_sz = "{} {}".format(sz_fmt, sz_mags[sz_mag]).format(int_sz)
                if int_sz <= 1024 or sz_mag + 1 >= len(sz_mags):
                    break
                int_sz /= 1024
                sz_mag += 1
                sz_fmt = "{:,.1f}"

            if w and h:
                str_sz += " | {}×{}".format(w, h)

        return str_sz

    def util_subdomain_is_valid(self, subdomain : str):
        """Check if subdomain matches URL domain constraints:

        One or more characters.
        Must start with [A-Za-z].
        All other characters must be [A-Za-z0-9-]."""
        return  len(subdomain) > 0 and \
                subdomain[0].isalnum() and \
                ((subdomain[1:].replace("-", "").isalnum() and len(subdomain) > 1) or \
                len(subdomain) == 1)

    def util_subdomain_to_string(self, subdomain : str):
        """Get subdomain as URL."""
        return "<https://{}.fandom.com/>".format(escape(subdomain.lower(), mass_mentions = True))

    def util_color_to_string(self, color : discord.Color):
        """Get color as #RRGGBB or "None"."""
        if color:
            return str(color)
        else:
            return "default"

    def util_color_from_string(self, color : str):
        """Get color value from the given string. Can return None if "none" or "default" or throws ValueError if invalid."""
        if not color or len(color) == 0 or color.lower() == "none" or color.lower() == "default":
            return None
        else:
            prefix = ""
            try:
                if color.startswith("#"):
                    prefix = "#"
                    color = color[1:]
                if color.startswith("0x"):
                    prefix = "0x"
                    color = color[2:]

                if len(color) == 6:
                    # RRGGBB or #RRGGBB or 0xRRGGBB
                    return discord.Color(value=int(color, 16))
                elif prefix == "#" and len(color) == 3:
                    # #RGB -> RRGGBB
                    color = color[0] + color[0] + color[1] + color[1] + color[2] + color[2]
                    return discord.Color(value=int(color, 16))
                elif prefix != "#" and len(color) <= 6 and len(color) > 0:
                    # 0xRRGGBB or RRGGBB
                    return discord.Color(value=int(color, 16))
                else:
                    # #X with length != 6 and != 3
                    raise ValueError("Invalid RRGGBB format.")
            except ValueError:
                # check if hex parse failed because it was a named color
                defcolors = [func for func in dir(discord.Color) \
                        if callable(getattr(discord.Color, func)) and \
                        not func.startswith("_") and \
                        not func.startswith("from_") and \
                        not func.startswith("to_")]
                for defcolor in defcolors:
                    if color.lower() == defcolor.lower():
                        return getattr(discord.Color, defcolor)()
                # wasn't a named color, re-raise
                raise


    def util_string_cut(self, content, length, word_cut = 100):
        """Cuts off text after a given length, preferring a certain "word length"."""
        # loop after possible modification
        #input_content_length = str(len(content))
        content = content.strip()
        cut_point = 0
        prev_cut_point = 0
        pos = 0
        for char in content:
            # set "cut" points
            if char == " " or char == "\n" or char == "\t" or char == "-" or char == "]":
                cut_point = pos

            pos += 1

            # cut here; no more looping
            if pos > length:
                if prev_cut_point - 3 < length and prev_cut_point + word_cut - 3 >= length:
                    # last word is too long, cut abruptly and append "..."
                    content = content[:length - 3] + "..."
                else:
                    # last word is acceptable
                    content = content[:prev_cut_point + 1] + "..."
                break
            else:
                prev_cut_point = cut_point
        #print("length: {} cut_at: {} wcut: {} rescut: {}".format(input_content_length, length, word_cut, str(len(content))))
        return content

    @commands.group(aliases=["wikiaset"])
    @checks.mod_or_permissions(manage_guild=True)
    async def fandomset(self, ctx):
        """FANDOM Wiki module settings."""
        pass

    @fandomset.command(name="default", aliases=["defaultwiki", "defaultfandom", "defaultwikia"])
    @checks.mod_or_permissions(manage_guild=True)
    async def fandomset_default(self, ctx, subdomain = None):
        """Set the default wiki for this server."""
        if ctx.guild is None:
            await ctx.send(error("You cannot set a default wiki in private messages with me. Use the `fandomset default` command in a server."))
            return

        if subdomain:
            if self.util_subdomain_is_valid(subdomain):
                subdomain_s = self.util_subdomain_to_string(subdomain)
                await self.config.guild(ctx.guild).default_wikia.set(subdomain.lower())
                await ctx.send(info("The default wiki for this server is now: {}".format(subdomain_s)))
            else:
                await ctx.send(error("That subdomain is not valid."))
        else:
            subdomain = await self.config.guild(ctx.guild).default_wikia()
            subdomain_s = self.util_subdomain_to_string(subdomain)
            await ctx.send(info("The default wiki for this server is currently: {}".format(subdomain_s)))

    @fandomset.command(name="accentcolor", aliases=["accent", "accentcolour", "color", "colour"])
    @checks.mod_or_permissions(manage_guild=True)
    async def fandomset_accentcolor(self, ctx, subdomain, color = None):
        """Set the accent color to use with each subdomain."""
        if ctx.guild is None:
            await ctx.send(error("You cannot set an accent color in private messages with me. Use the `fandomset accentcolor` command in a server."))
            return

        if self.util_subdomain_is_valid(subdomain):
            subdomain_s = self.util_subdomain_to_string(subdomain)
            if color:
                try:
                    color_o = self.util_color_from_string(color)
                    color_s = self.util_color_to_string(color_o)
                    async with self.config.guild(ctx.guild).accent_color_map() as colors:
                        if color_o:
                            colors[subdomain] = color_o.value
                        elif subdomain in colors:
                            del colors[subdomain]
                    await ctx.send(info("The accent color for {} results for this server is now: {}".format(subdomain_s, color_s)))
                except ValueError:
                    await ctx.send(error("That color is not valid."))
            else:
                color_o = None
                async with self.config.guild(ctx.guild).accent_color_map() as colors:
                    if subdomain in colors:
                        color_o = discord.Color(colors[subdomain])
                if color_o:
                    color_s = self.color_to_string(color_o)
                    await ctx.send(info("The accent color for {} results for this server is currently: {}".format(subdomain_s, color_s)))
        else:
            await ctx.send(error("That subdomain is not valid."))

    @fandomset.command(name="tag", aliases=["tagspoilers", "tagspoiler", "spoilers", "spoiler"])
    @checks.mod_or_permissions(manage_guild=True)
    async def fandomset_tag(self, ctx, value : bool = None):
        """Sets whether to tag wiki results as spoilers on this server."""
        if ctx.guild is None:
            await ctx.send(error("You cannot set whether to tag in private messages with me. Use the `fandomset tag` command in a server."))
            return

        if value is None:
            value = not await self.config.guild(ctx.guild).tag_as_spoilers()

        await self.config.guild(ctx.guild).tag_as_spoilers.set(value)
        if value:
            await ctx.send(info("I will tag all wiki results as spoilers."))
        else:
            await ctx.send(info("I will not tag wiki results as spoilers."))

