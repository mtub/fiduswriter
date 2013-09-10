import uuid

from ws.base import BaseWebSocketHandler
from logging import info, error
from tornado.escape import json_decode

from text.models import AccessRight, Text
from avatar.templatetags.avatar_tags import avatar_url

class DocumentWS(BaseWebSocketHandler):
    sessions = dict()

    def open(self, document_id):
        print 'Websocket opened'
        self.user = self.get_current_user()
        self.document = document_id 
        document = Text.objects.filter(id=self.document)
        if len(document) > 0:
            document = document[0]
            access_right = AccessRight.objects.filter(text=document, user=self.user)
            if document.owner == self.user or len(access_right) > 0:
                if len (access_right) > 0:
                    self.access_right = access_right[0]
                else:
                    self.access_right = 'w'
                if self.document not in DocumentWS.sessions:
                    DocumentWS.sessions[self.document]=dict()
                    self.id = 0
                else:
                    self.id = max(DocumentWS.sessions[self.document])+1
                DocumentWS.sessions[self.document][self.id] = self
                self.write_message({
                    "type": 'welcome',
                    "key": self.id
                    })
                DocumentWS.send_participant_list(self.document)

    def on_message(self, message):
        parsed = json_decode(message)
        if parsed["type"]=='chat':
            chat = {
                "id": str(uuid.uuid4()),
                "body": parsed["body"],
                "from": self.user.id,
                "type": 'chat'
                }
            if self.document in DocumentWS.sessions:
                DocumentWS.send_updates(chat, self.document)
        elif parsed["type"]=='transform':
            chat = {
                "id": str(uuid.uuid4()),
                "change": parsed["change"],
                "from": self.user.id,
                "type": 'transform'
                }
            if self.document in DocumentWS.sessions:
                DocumentWS.send_updates(chat, self.document, self.id)            

    def on_close(self):
        print 'Websocket closed'
        if self.document in DocumentWS.sessions:
            del DocumentWS.sessions[self.document][self.id]
            if DocumentWS.sessions[self.document]:
                chat = {
                    "type": 'take_control'
                    }
                DocumentWS.sessions[self.document][min(DocumentWS.sessions[self.document])].write_message(chat)
                DocumentWS.send_participant_list(self.document)
            else:
                del DocumentWS.sessions[self.document]

    @classmethod
    def send_participant_list(cls, document):
        if document in DocumentWS.sessions:
            participant_list = []
            for waiter in cls.sessions[document].keys():
                participant_list.append({
                    'key':waiter,
                    'id':cls.sessions[document][waiter].user.id,
                    'name':cls.sessions[document][waiter].user.readable_name,
                    'avatar':avatar_url(cls.sessions[document][waiter].user,80)
                    })
            chat = {
                "participant_list": participant_list,
                "type": 'connections'
                }
            DocumentWS.send_updates(chat, document)

    @classmethod
    def send_updates(cls, chat, document, sender_id=None):
        info("sending message to %d waiters", len(cls.sessions[document]))
        for waiter in cls.sessions[document].keys():
            if cls.sessions[document][waiter].id != sender_id:
                try:
                    cls.sessions[document][waiter].write_message(chat)
                except:
                    error("Error sending message", exc_info=True)            
         