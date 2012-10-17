#!python
# -*- coding:UTF-8 -*-

import pygtk
pygtk.require('2.0')
import gtk
import glib
import gobject
import gtksourceview2
import pango
import webkit

import platform
import os
import threading
import time
import sys
import urllib
import urllib2
import json
import htmlentitydefs
import re

import markdown

try:
    proxy = os.environ['HTTPS_PROXY'] or os.environ['HTTP_PROXY']
except:
    proxy = None
    pass
if proxy:
    proxy_handler = urllib2.ProxyHandler({"https": proxy})
    opener = urllib2.build_opener(proxy_handler)
    urllib2.install_opener(opener)

font_size = 14
font_default = 'Ricty'
font_serif = 'Ricty'
font_sans_serif = 'Ricty'
font_monospace = 'Ricty'
settings = webkit.WebSettings()
settings.set_property('serif-font-family', font_serif)
settings.set_property('sans-serif-font-family', font_sans_serif)
settings.set_property('monospace-font-family', font_monospace)
settings.set_property('default-font-family', font_default)
settings.set_property('default-font-size', font_size)
if proxy:
    try:
        import ctypes
        if platform.system() == 'Windows':
            libgobject = ctypes.CDLL('libgobject-2.0-0.dll')
            libsoup = ctypes.CDLL('libsoup-2.4-1.dll')
            libwebkit = ctypes.CDLL('libwebkit-1.0-2.dll')
        else:
            libgobject = ctypes.CDLL('libgobject-2.0.so.0')
            libsoup = ctypes.CDLL('libsoup-2.4.so.1')
            libwebkit = ctypes.CDLL('libwebkit-1.0.so.2')
        proxy_uri = libsoup.soup_uri_new(proxy)
        session = libwebkit.webkit_get_default_session()
        libgobject.g_object_set(session, "proxy-uri", proxy_uri, None)
        libsoup.soup_uri_free(proxy_uri)
    except:
        pass


def decode_entities(s):
    f = lambda m: unichr(htmlentitydefs.name2codepoint[m.group(1)])
    return re.sub('&([^;]+);', f, s)


def load_config():
    path = os.path.join(glib.get_user_config_dir(), 'kobita')
    if not os.path.isdir(path):
        os.mkdir(path)
        return None
    path = os.path.join(path, 'config')
    if not os.path.isfile(path):
        return None
    with open(path) as f:
        return json.load(f)


def save_config(config):
    path = os.path.join(glib.get_user_config_dir(), 'kobita')
    if not os.path.isdir(path):
        os.mkdir(path)
    path = os.path.join(path, 'config')
    with open(path, 'w') as f:
        json.dump(config, f)


class ListView(gtk.Window):
    def __init__(self, **args):
        gtk.Window.__init__(self, **args)

        self.set_title('Kobita')
        self.set_default_size(800, 600)
        self.set_border_width(5)
        self.connect('delete-event', gtk.main_quit)
        self.connect('show', self.on_show)

        hbox = gtk.HBox(True, 5)

        vbox = gtk.VBox(False, 5)
        sw = gtk.ScrolledWindow()
        sw.set_shadow_type(gtk.SHADOW_ETCHED_OUT)
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.tv = gtk.TreeView(model=gtk.ListStore(str, str))
        fontdesc = pango.FontDescription("%s %d" % (font_default, font_size))
        self.tv.modify_font(fontdesc)
        self.tv.set_grid_lines(gtk.TREE_VIEW_GRID_LINES_BOTH)
        self.tv.get_selection().connect('changed', self.on_selection_changed)
        self.tv.set_headers_visible(False)
        self.tv.connect('row-activated', self.on_row_activated)
        renderer = gtk.CellRendererText()
        tvc = gtk.TreeViewColumn('uuid', renderer, text=0)
        tvc.set_visible(False)
        self.tv.append_column(tvc)
        tvc = gtk.TreeViewColumn('title', renderer, text=1)
        self.tv.append_column(tvc)
        sw.add(self.tv)
        vbox.pack_start(sw, True, True, 0)
        button = gtk.Button("New Entry")
        button.connect('clicked', self.on_new_entry)
        vbox.pack_end(button, False, False, 0)
        hbox.pack_start(vbox, False, True, 0)

        sw = gtk.ScrolledWindow()
        sw.set_shadow_type(gtk.SHADOW_ETCHED_OUT)
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.view = webkit.WebView()
        self.view.set_settings(settings)
        sw.add(self.view)
        hbox.pack_start(sw, False, True, 0)

        self.add(hbox)

    def on_new_entry(self, w):
        self.tv.set_sensitive(False)
        self.iv = ItemView(self.token, None)
        self.iv.connect('delete-event', self.on_item_view_closed)
        self.iv.show_all()

    def on_item_view_closed(self, w, d):
        self.tv.set_sensitive(True)
        self.emit('show')

    def on_selection_changed(self, sel):
        if sel.get_selected()[1] is None:
            return
        uuid = self.tv.get_model().get(sel.get_selected()[1], 0)[0]
        item = filter(lambda x: x['uuid'] == uuid, self.data)[0]
        self.view.load_html_string(item['body'], '')

    def on_row_activated(self, tv, path, vc):
        self.set_sensitive(False)
        self.iv = ItemView(self.token, self.data[path[0]]['uuid'])
        self.iv.connect('delete-event', self.on_item_view_closed)
        self.iv.show_all()

    def on_show(self, e):
        config = load_config()
        if not config is None and 'token' in config.keys():
            auth = config
        else:
            auth = self.login()
        if auth is None:
            gtk.main_quit()
            return
        self.url_name = auth['url_name']

        if config is None or not 'token' in config.keys():
            try:
                data = urllib.urlencode(auth)
                r = urllib2.urlopen('https://qiita.com/api/v1/auth', data)
                self.token = json.load(r)['token']
                save_config({
                    'url_name': auth['url_name'], 'token': self.token})
            except:
                dialog = gtk.MessageDialog(None,
                    gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_ERROR,
                    gtk.BUTTONS_CLOSE, 'Login Failed')
                dialog.run()
                dialog.destroy()
                gtk.main_quit()
                return
        else:
            self.token = config['token']
            self.url_name = config['url_name']

        th = threading.Thread(target=self.reload_item)
        th.setDaemon(True)
        th.start()

    def login(self):
        dialog = gtk.Dialog(
            'Kobita Login',
            self,
            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
            (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
             gtk.STOCK_OK, gtk.RESPONSE_OK))

        sgroup = gtk.SizeGroup(gtk.SIZE_GROUP_HORIZONTAL)
        hbox = gtk.HBox(False, 5)
        label = gtk.Label("User")
        sgroup.add_widget(label)
        hbox.add(label)
        user = gtk.Entry()
        hbox.add(user)
        dialog.vbox.add(hbox)
        label = gtk.Label("Password")
        sgroup.add_widget(label)
        hbox = gtk.HBox(False, 5)
        hbox.add(label)
        password = gtk.Entry()
        password.set_visibility(False)
        hbox.add(password)
        dialog.vbox.add(hbox)
        dialog.show_all()
        try:
            if dialog.run() == gtk.RESPONSE_OK:
                return {'url_name': user.get_text(),
                        'password': password.get_text()}
        finally:
            dialog.destroy()
        return None

    def reload_item(self):
        gtk.threads_enter()
        self.set_sensitive(False)
        gtk.threads_leave()

        url = 'https://qiita.com/api/v1/users/%s/items?%s' % (
            self.url_name, urllib.urlencode({'token': self.token}))
        r = urllib2.urlopen(url)
        self.data = json.load(r)

        model = self.tv.get_model()
        model.clear()

        for item in self.data:
            gtk.threads_enter()
            model.append((item['uuid'], decode_entities(item['title'])))
            gtk.threads_leave()

        gtk.threads_enter()
        self.set_sensitive(True)
        gtk.threads_leave()


class ItemView(gtk.Window):
    def __init__(self, token, uuid, **args):
        gtk.Window.__init__(self, **args)

        self.token = token
        self.uuid = uuid
        self.timer = -1

        self.set_title('Kobita')
        self.connect('show', self.on_show)
        self.set_default_size(800, 600)
        self.set_border_width(5)

        hbox = gtk.HBox(True, 5)

        vbox = gtk.VBox(False, 5)
        sw = gtk.ScrolledWindow()
        sw.set_shadow_type(gtk.SHADOW_ETCHED_OUT)
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.buffer = gtksourceview2.Buffer()
        self.buffer.set_max_undo_levels(1000)
        self.buffer.connect('changed', self.on_changed)
        self.edit = gtksourceview2.View(self.buffer)
        sw.add(self.edit)
        vbox.pack_start(sw, True, True, 0)
        hhbox = gtk.HBox(False, 5)
        self.tags = []
        for n in range(5):
            tag = gtk.Entry()
            tag.set_usize(20, -1)
            hhbox.add(tag)
            self.tags.append(tag)
        vbox.pack_start(hhbox, False, False, 0)
        hhbox = gtk.HBox(True, 5)
        self.check = gtk.CheckButton('Private')
        hhbox.add(self.check)
        button = gtk.Button("Publish")
        button.connect('clicked', self.on_publish)
        hhbox.add(button)
        vbox.pack_end(hhbox, False, False, 0)
        hbox.pack_start(vbox, False, True, 0)

        sw = gtk.ScrolledWindow()
        sw.set_shadow_type(gtk.SHADOW_ETCHED_OUT)
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.view = webkit.WebView()
        self.view.set_settings(settings)
        sw.add(self.view)
        hbox.pack_start(sw, False, True, 0)

        self.add(hbox)

    def on_timeout(self):
        gtk.threads_enter()
        self.timer = -1
        text = self.buffer.get_text(*self.buffer.get_bounds())
        lines = text.split("\n", 1)
        title = lines[0]
        body = len(lines) == 2 and lines[1] or ''
        text = "# %s\n%s" % (title, body)
        html = markdown.markdown(text, ['tables'])
        self.view.load_html_string(html, '')
        gtk.threads_leave()

    def on_changed(self, tv):
        if self.timer != -1:
            gobject.source_remove(self.timer)
        self.timer = gobject.timeout_add(1000, self.on_timeout)

    def on_show(self, e):
        if self.uuid is None:
            return
        th = threading.Thread(target=self.reload_item)
        th.setDaemon(True)
        th.start()

    def reload_item(self):
        gtk.threads_enter()
        self.set_sensitive(False)
        gtk.threads_leave()

        url = 'https://qiita.com/api/v1/items/%s?%s' % (
            self.uuid, urllib.urlencode({'token': self.token}))
        r = urllib2.urlopen(url)
        self.data = json.load(r)

        gtk.threads_enter()
        text = "%s\n%s" % (self.data['title'], self.data['raw_body'])
        self.buffer.begin_not_undoable_action()
        self.buffer.set_text(text)
        self.buffer.end_not_undoable_action()
        self.buffer.place_cursor(self.buffer.get_start_iter())
        for n in range(len(self.data['tags'])):
            self.tags[n].set_text(self.data['tags'][n]['name'])
        gtk.threads_leave()

        gtk.threads_enter()
        self.check.set_active(self.data['private'])
        self.set_sensitive(True)
        gtk.threads_leave()

    def on_publish(self, w):
        text = self.buffer.get_text(*self.buffer.get_bounds())
        lines = text.split("\n", 1)
        title = lines[0]
        body = len(lines) == 2 and lines[1] or ''
        payload = json.dumps({
            'token': self.token,
            'title': title,
            'body': body,
            'tags': filter(lambda x: len(x['name']) > 0,
                [{'name': x.get_text()} for x in self.tags]),
            'private': self.check.get_active()
        })
        if self.uuid is None:
            url = 'https://qiita.com/api/v1/items'
            header = {'Content-Type': 'application/json'}
            req = urllib2.Request(url, payload, header)
        else:
            url = 'https://qiita.com/api/v1/items/%s' % self.uuid
            header = {
                'Content-Type': 'application/json',
                'X-HTTP-Method-Override': 'PUT'
            }
            req = urllib2.Request(url, payload, header)
        r = urllib2.urlopen(req)
        self.uuid = json.load(r)['uuid']


def main():
    lv = ListView()
    lv.show_all()
    gobject.threads_init()
    gtk.main()

if __name__ == "__main__":
    main()

# vim:set ts=4 sw=4 et ai:
