from redbot.core import commands, checks, Config
from redbot.core.utils.chat_formatting import pagify
import discord
import random
import requests
import re
import enum
from bs4 import BeautifulSoup
from .pastebin import PasteBin
import constants
import dclasses

class LoginError(enum.Enum):
    NONE = 0
    INCORRECT_USERNAME = 1,
    INCORRECT_PASSWORD = 2,
    LOGIN_ATTEMPTS_EXCEEDED = 3,
    UNKNOWN = 4

class MXL(commands.Cog):
    """Median XL utilities."""

    def __init__(self):
        self.auctions_endpoint = 'https://forum.median-xl.com/api.php?mode=tradecenter'
        self.tradecenter_enpoint = 'https://forum.median-xl.com/tradegold.php'
        self.forum_login_endpoint = 'https://forum.median-xl.com/ucp.php?mode=login'
        self.forum_logout_endpoint = 'https://forum.median-xl.com/ucp.php?mode=logout&sid={}'
        self.armory_login_endpoint = 'https://tsw.vn.cz/acc/login.php' # POST
        self.armory_logout_endpoint = 'https://tsw.vn.cz/acc/logout.php' # GET
        self.armory_index_endpoint = 'https://tsw.vn.cz/acc/index.php'
        self.armory_character_endpoint = 'https://tsw.vn.cz/acc/char.php?name={}'

        default_config = {
            'forum_username': '',
            'forum_password': '',
            'forum_cookies': {
                'MedianXL_u': '',
                'MedianXL_k': '',
                'MedianXL_sid': ''
            },
            'armory_username': '',
            'armory_password': '',
            'armory_cookies': {
                'PHPSESSID': ''
            },
            'pastebin_api_key': ''
        }
        self._config = Config.get_conf(self, identifier=134621854878007298)
        self._config.register_global(**default_config)

    @commands.guild_only()
    @commands.group(name="mxl")
    async def mxl(self, ctx):
        """A bunch of stuff for the Median XL Diablo II mod."""

        pass

    @mxl.group(name="auctions", invoke_without_command=True)
    async def auctions(self, ctx):
        """MXL auction utilities."""

        if ctx.invoked_subcommand is None:
            await ctx.invoke(self.auctions_list)

    @auctions.command(name="list")
    @commands.cooldown(1, 60, discord.ext.commands.BucketType.user)
    async def auctions_list(self, ctx):
        """
        Prints all the currently active auctions.

        If there are more than 5 active auctions, prints them in a DM instead.
        """
        api_response = requests.get(self.auctions_endpoint)
        if api_response.status_code != 200:
            await ctx.send('Couldn\'t contact the MXL API. Try again later.')
            return

        embeds = self._get_auction_embeds(api_response.json()['auctions'])
        if not embeds:
            await ctx.send('There are no active auctions at the moment.')
            return

        channel = ctx.channel
        if len(embeds) > 5:
            channel = ctx.author.dm_channel or await ctx.author.create_dm()

        for embed in embeds:
            await channel.send(embed=embed)

    @auctions.command(name="search")
    async def auctions_search(self, ctx, *, title: str):
        """
        Searches the titles of the currently active auctions and prints the results.

        If there are more than 5 results, prints them in a DM instead.
        """
        api_response = requests.get(self.auctions_endpoint)
        if api_response.status_code != 200:
            await ctx.send('Couldn\'t contact the MXL API. Try again later.')
            return

        embeds = self._get_auction_embeds(api_response.json()['auctions'])
        matching_auctions = [embed for embed in embeds if re.search(title, embed.title, re.IGNORECASE)]
        if not matching_auctions:
            await ctx.send('There are no active auctions that match that description at the moment.')
            return

        channel = ctx.channel
        if len(matching_auctions) > 5:
            channel = ctx.author.dm_channel or await ctx.author.create_dm()

        for embed in matching_auctions:
            await channel.send(embed=embed)

    @mxl.group(name="config")
    @checks.is_owner()
    async def config(self, ctx):
        """Configures forum account login details for item pricechecking."""

        pass

    @config.command(name="forum_username")
    async def forum_username(self, ctx, username: str = None):
        """Gets/sets the username to be used to log into the forums."""

        if username is None:
            current_username = await self._config.forum_username()
            await ctx.send(f'Current username: {current_username}')
            return

        await self._config.forum_username.set(username)
        await ctx.channel.send('MXL username set successfully.')

    @config.command(name="forum_password")
    async def forum_password(self, ctx, password: str = None):
        """Gets/sets the password to be used to log into the forums."""

        if password is None:
            channel = ctx.author.dm_channel or await ctx.author.create_dm()
            current_password = await self._config.forum_password()
            await channel.send(f'Current password: {current_password}')
            return

        await self._config.forum_password.set(password)
        await ctx.message.delete()
        await ctx.channel.send('MXL password set successfully.')

    @config.command(name="armory_username")
    async def armory_username(self, ctx, username: str = None):
        """Gets/sets the username to be used to log into the armory."""

        if username is None:
            current_username = await self._config.armory_username()
            await ctx.send(f'Current username: {current_username}')
            return

        await self._config.armory_username.set(username)
        await ctx.channel.send('MXL armory username set successfully.')

    @config.command(name="armory_password")
    async def armory_password(self, ctx, password: str = None):
        """Gets/sets the password to be used to log into the armory."""

        if password is None:
            channel = ctx.author.dm_channel or await ctx.author.create_dm()
            current_password = await self._config.armory_password()
            await channel.send(f'Current password: {current_password}')
            return

        await self._config.armory_password.set(password)
        await ctx.message.delete()
        await ctx.send('MXL armory password set successfully.')

    @config.command(name="pastebin_api_key")
    async def pastebin_api_key(self, ctx, key: str = None):
        """Gets/sets the API key to be used when creating pastebins."""

        if key is None:
            channel = ctx.author.dm_channel or await ctx.author.create_dm()
            current_api_key = await self._config.pastebin_api_key()
            await channel.send(f'Current API key: {current_api_key}')
            return

        await self._config.pastebin_api_key.set(key)
        await ctx.send('PasteBin API key set successfully.')

    @mxl.command(name="pricecheck", aliases=["pc"])
    async def pricecheck(self, ctx, *, item: str):
        """
        Checks all TG transactions for the provided item/string.

        Note: Only looks at the first 25 results.
        """

        config = await self._config.all()
        if not config['forum_username']:
            await ctx.send(f'No forum account is currently configured for this server. Use `{ctx.prefix}mxl config` to set one up.')
            return

        def not_logged_in_function(tag):
            return 'We\'re sorry' in tag.text

        def no_transactions_found(tag):
            return 'No transactions found.' in tag.text

        def escape_underscore(text):
            return text.replace('_', '\\_')

        pricecheck_response = requests.post(self.tradecenter_enpoint, data={'search': item, 'submit': ''}, cookies=config['forum_cookies'])
        dom = BeautifulSoup(pricecheck_response.text, 'html.parser')
        if dom.find(not_logged_in_function):
            error, config = await self._forum_login()
            if error == LoginError.INCORRECT_USERNAME:
                await ctx.send(f'Incorrect forum username. Please set a valid one using `{ctx.prefix}mxl config username`.')
                return
            elif error == LoginError.INCORRECT_PASSWORD:
                await ctx.send(f'Incorrect forum password. Please set the proper one using `{ctx.prefix}mxl config password`.')
                return
            elif error == LoginError.LOGIN_ATTEMPTS_EXCEEDED:
                await ctx.send(f'Maximum login attempts exceeded. Please login to the forum manually (with the configured account) and solve the CAPTCHA.')
                return
            elif error == LoginError.UNKNOWN:
                await ctx.send('Unknown error during login.')
                return

            pricecheck_response = requests.post(self.tradecenter_enpoint, data={'search': item, 'submit': ''}, cookies=config['forum_cookies'])
            dom = BeautifulSoup(pricecheck_response.text, 'html.parser')
            if dom.find(not_logged_in_function):
                await ctx.send('Couldn\'t login to the forums. Please report this to the plugin author.')
                return

        if dom.tbody.find(no_transactions_found):
            await ctx.send('No results found.')
            return

        pc_results_raw = [item for item in dom.tbody.contents if item != '\n']
        message = ''
        for result in pc_results_raw:
            columns = [column for column in result.contents if column != '\n']
            message += f'--------------------------\n**Transaction note**: {escape_underscore(columns[3].text)}\n**From**: {escape_underscore(columns[0].a.text)}\n**To**: {escape_underscore(columns[2].a.text)}\n**TG**: {columns[1].div.text}\n**Date**: {columns[4].text}\n'

        for page in pagify(message, delims=['--------------------------']):
            embed = discord.Embed(title=f'Auctions for {item}', description=page)
            await ctx.send(embed=embed)


    @mxl.group(name="logout")
    @checks.is_owner()
    async def logout(self, ctx):
        """Logs out the current forum/armory session."""

        pass

    @logout.command(name="forum")
    async def logout_forum(self, ctx):
        """
        Logs out the current forum session.

        Use if you want to change the forum user.
        """

        config = await self._config.all()
        if not config['forum_cookies']['MedianXL_sid']:
            await ctx.send('Not logged in.')
            return

        logout_response = requests.get(self.forum_logout_endpoint.format(config['forum_cookies']['MedianXL_sid']), cookies=config['forum_cookies'])
        dom = BeautifulSoup(logout_response.text, 'html.parser')
        if dom.find(title='Login'):
            config['forum_cookies'] = {
                'MedianXL_u': '',
                'MedianXL_k': '',
                'MedianXL_sid': ''
            }
            await self._config.set(config)
            await ctx.send('Forum account logged out successfully.')
            return

        if dom.find(title='Logout'):
            await ctx.send('Forum logout attempt was unsuccessful.')
            return

        await ctx.send('Unknown error during forum logout.')

    @logout.command(name="armory")
    async def logout_armory(self, ctx):
        """
        Logs out the current armory session.

        Use if you want to change the armory user.
        """

        config = await self._config.all()
        if not config['armory_cookies']['PHPSESSID']:
            await ctx.send('Not logged in.')
            return

        logout_response = requests.get(self.armory_logout_endpoint, cookies=config['armory_cookies'])
        dom = BeautifulSoup(logout_response.text, 'html.parser')
        if not dom.find(action='login.php'):
            await ctx.send('Unknown error during armory logout.')

        config['armory_cookies']['PHPSESSID'] = ''
        await self._config.set(config)
        await ctx.send('Armory account logged out successfully.')
        return

    @mxl.group(name="armory")
    async def armory(self, ctx):
        """TSW (not)armory utilities."""

        pass

    @armory.command(name="dump")
    async def armory_dump(self, ctx, *characters):
        """Dumps all the items of the supplied characters.

        Dumps the supplied character's items (stash, inventory, cube, equipped) into a formated string to be posted on the forums.
        The characters must be publicly viewable - log into http://tsw.vn.cz/acc/ to configure visibility.
        """

        config = await self._config.all()
        if not config['pastebin_api_key']:
            await ctx.send(f'Pastebin API key hasn\'t been configured yet. Configure one using `{ctx.prefix}mxl config pastebin_api_key`.')
            return

        if not config['armory_username']:
            await ctx.send(f'Armory account hasn\'t been configured yet. Configure one using `{ctx.prefix}mxl config armory_username/armory_password`.')
            return

        items = dclasses.ItemDump()
        for character in characters:
            character_response = requests.get(self.armory_character_endpoint.format(character), cookies=config['armory_cookies'])
            dom = BeautifulSoup(character_response.text, 'html.parser')
            if dom.find(action='login.php'):
                error, config = await self._armory_login()
                if error:
                    await ctx.send('Incorrect armory username/password or armory is not reachable.')
                    return
                character_response = requests.get(self.armory_character_endpoint.format(character), cookies=config['armory_cookies'])
                dom = BeautifulSoup(character_response.text, 'html.parser')

            if 'not allowed' in dom.h1.text:
                await ctx.send(f'{character}\'s armory is private - skipping. Please log into the armory and make it publicly viewable to dump its items.')
                continue

            item_dump = dom.find_all(class_='item-wrapper')
            self._scrape_items(item_dump, items)

        if not items:
            await ctx.send('No items found.')
            return

        post = items.to_trade_post()
        pastebin_link = await self._create_pastebin(post, f'MXL trade post for characters: {", ".join(characters)}')
        channel = ctx.author.dm_channel or await ctx.author.create_dm()
        if pastebin_link:
            await channel.send(f'Dump successful. Here you go: {pastebin_link}')
            return

        await ctx.send('Couldn\'t create the trade post pastebin - 24h limit is probably reached. Check your DMs.')
        for page in pagify(post):
            await channel.send(embed=discord.Embed(description=page))

    async def _forum_login(self):
        config = await self._config.all()
        session_id = requests.get(self.tradecenter_enpoint).cookies['MedianXL_sid']
        login_response = requests.post(self.forum_login_endpoint, data={'username': config['forum_username'], 'password': config['forum_password'], 'autologin': 'on', 'login': 'Login', 'sid': session_id})
        dom = BeautifulSoup(login_response.text, 'html.parser')
        error = dom.find(class_='error')
        if error is None:
            config['forum_cookies'] = {
                'MedianXL_sid': login_response.history[0].cookies['MedianXL_sid'],
                'MedianXL_k': login_response.history[0].cookies['MedianXL_k'],
                'MedianXL_u': login_response.history[0].cookies['MedianXL_u']
            }
            await self._config.set(config)
            return LoginError.NONE, config

        if 'incorrect username' in error.text:
            return LoginError.INCORRECT_USERNAME, None

        if 'incorrect password' in error.text:
            return LoginError.INCORRECT_PASSWORD, None

        if 'maximum allowed number of login attempts' in error.text:
            return LoginError.LOGIN_ATTEMPTS_EXCEEDED, None

        return LoginError.UNKNOWN, None

    async def _armory_login(self):
        config = await self._config.all()
        session_id = requests.get(self.armory_index_endpoint).cookies['PHPSESSID']
        login_response = requests.post(self.armory_login_endpoint, data={'user': config['armory_username'], 'pass': config['armory_password']}, cookies={'PHPSESSID': session_id})
        dom = BeautifulSoup(login_response.text, 'html.parser')
        if not dom.contents:
            config['armory_cookies'] = {
                'PHPSESSID': session_id
            }
            await self._config.set(config)
            return False, config

        return True, None

    def _scrape_items(self, item_dump, items):
        for item in item_dump:
            if item.th:
                continue

            item_name = item.span.text
            set_match = re.search('\[([^\]]+)', item.span.text)

            if item_name in constants.IGNORED_ITEMS:
                continue

            if set_match:
                set_name = set_match.group(1)
                item_name = item_name.split('[')[0].strip()
                items.increment_set_item(set_name, item_name)
                continue

            if item_name in constants.SU_ITEMS:
                items.increment_su(item_name)
                continue

            if 'Hanfod' in item_name:
                items.increment_su('Hanfod Tân')
                continue

            if item_name == 'Jewel':
                item.increment_other('Jewel')
                continue

            if item_name in constants.SSU_ITEMS:
                items.increment_ssu(item_name)
                continue

            if item_name in constants.SSSU_ITEMS:
                items.increment_sssu(item_name)
                continue

            if item_name in constants.RUNEWORDS:
                items.increment_rw(item_name)
                continue

            if item_name in constants.AMULETS:
                items.increment_amulet(item_name)
                continue

            if item_name in constants.RINGS:
                items.increment_ring(item_name)
                continue

            if item_name in constants.JEWELS:
                items.increment_jewel(item_name)
                continue

            if item_name in constants.QUIVERS:
                items.increment_quiver(item_name)
                continue

            if item_name in constants.MOS:
                items.increment_mo(item_name)
                continue

            if item.span['class'][0] == 'color-white' or item.span['class'][0] == 'color-blue':
                base_name = item_name + ' [eth]' if '[ethereal]' in item.text else ''.join(item_name.split('Superior '))
                items.increment_rw_base(base_name)
                continue

            if item.span['class'][0] == 'color-yellow':
                items.increment_shrine_base(item_name)
                continue

            if item_name in constants.CHARMS:
                items.increment_charm(item_name)
                continue

            shrine_match = re.search('Shrine \(([^\)]+)', item_name)
            if shrine_match:
                shrine_name = item_name.split('(')[0].strip()
                amount = int(shrine_match.group(1)) / 10
                items.increment_shrine(shrine_name, amount)
                continue

            if item_name in constants.SHRINE_VESSELS:
                vessel_amount = int((re.search('Quantity: ([0-9]+)', item.find(class_='color-grey').text)).group(1))
                shrine_name = constants.VESSEL_TO_SHRINE[item_name]
                items.increment_shrine(shrine_name, vessel_amount)
                continue

            if item_name == 'Arcane Cluster':
                crystals_amount = int((re.search('Quantity: ([0-9]+)', item.find(class_='color-grey').text)).group(1))
                items.increment_other('Arcane Crystal', crystals_amount)
                continue

            AC_shards_match = re.search('Shards \(([^\)]+)', item_name)
            if AC_shards_match:
                amount = int(AC_shards_match.group(1)) / 5
                items.increment_other('Arcane Crystal', amount)
                continue

            if item_name in constants.TROPHIES:
                items.increment_trophy(item_name)
                continue

            items.increment_other(item_name)

    async def _create_pastebin(self, text, title=None):
        api_key = await self._config.pastebin_api_key()
        pb = PasteBin(api_key)
        pb_link = pb.paste(text, name=title, private='1', expire='1D')
        return None if 'Bad API request' in pb_link or 'Post limit' in pb_link else pb_link

    def _get_auction_embeds(self, raw_auctions):
        embeds = []
        for auction in raw_auctions:
            soup = BeautifulSoup(auction, 'html.parser')
            current_bid = soup.find(class_='coins').text
            number_of_bids = soup.div.div.find(title='Bids').next_sibling.strip()
            title = soup.h4.text
            time_left = soup.span.text.strip()
            started_by = soup.find(class_='username').text
            description = f'Started by: {started_by}\nCurrent bids: {number_of_bids}\nCurrent bid: {current_bid} TG\nTime left: {time_left}'
            image = soup.find(title='Image')
            embed = discord.Embed(title=title, description=description)
            if image is not None:
                embed.set_image(url=image['data-featherlight'])
            embeds.append(embed)

        return embeds
