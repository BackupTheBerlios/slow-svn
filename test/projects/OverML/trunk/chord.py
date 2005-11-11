from slow.pyexec.pyedsm.states import *
from math import log, floor
import random

MAX_ID = 2**160

def ring_dist(id1, id2):
    d = id2 - id1
    if d < 0:
        return MAX_ID + d
    else:
        return d

class ChordInit(State):
    "The start state."
    MAX_CONNECTION_TRIES = 10
    __TRY_COUNT = 0
    def __call__(self):
        self.__TRY_COUNT += 1
        if self.__TRY_COUNT <= self.MAX_CONNECTION_TRIES:
            yield self.ADVANCE_ONLY

class ChordRouter(MessageHandlerState):
    def handleMessage(self, message):
        views = self.db.view
        local_id = self.local_node.id
        dest_id  = message.addresses.dest

        dist = ring_dist(local_id, dest_id)
        log2_dist = int(floor( log(dist) / log(2) ))

        get_bucket = views['chord_fingertable'].bucket
        successor_nodes = None
        while log2_dist > 0 and not successor_nodes:
            successor_nodes = get_bucket(log2_dist)
            log2_dist -= 1

        if successor_nodes:
            neighbour = random.choice(successor_nodes)
            self.message_output.forward_message(message, neighbour)
        else:
            yield message

class ChordDB(MessageHandlerState):
    def handleMessage(self, message):
        self.db.addNodes([message.addresses.source, message.addresses.dest])
        yield self.TERMINATED

class JoinHandler(MessageHandlerState):
    def handleMessage(self, message):
        print message
        yield self.TERMINATED


############################################################
############################################################

class ChordRouter_unused(MessageHandlerState):
    __LOG_2 = log(2)
    def handleMessage(self, message):
        local_id = self.local_node.id
        dest_id  = message.addresses.dest

        views = self.db.view

        neighbour = views['chord_last_neighbour'].first_node()
        if dest_id == neighbour.id:
            self.forward_message(message, neighbour)
            return
        elif dest_id < neighbour.id:
            neighbour = None
            for next_neighbour in views['chord_neighbours'].iternodes():
                if next_neighbour.id > dest_id:
                    break
                neighbour = next_neighbour
            if neighbour:
                self.forward_message(message, neighbour)
            else:
                yield message
            return

        dist = ring_dist(local_id, dest_id)
        log2_dist = int(floor( log(dist) / self.__LOG_2 ))

        successor_nodes = views['chord_fingertable'].find_non_empty_bucket(
            -1, i=log2_dist)

        if successor_nodes:
            neighbour = random.choice(successor_nodes)
            self.message_output.forward_message(message, neighbour)
        else:
            yield message

