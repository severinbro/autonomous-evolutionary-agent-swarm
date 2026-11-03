"""Document tree node used by the block and inline parsers."""

CONTAINER_TYPES = frozenset([
    'document', 'block_quote', 'list', 'item', 'paragraph', 'heading',
    'emph', 'strong', 'link', 'image',
])


class ListData:
    __slots__ = ('type', 'tight', 'bullet_char', 'start', 'delimiter',
                 'padding', 'marker_offset')

    def __init__(self):
        self.type = None
        self.tight = True
        self.bullet_char = None
        self.start = None
        self.delimiter = None
        self.padding = None
        self.marker_offset = 0


class Node:
    __slots__ = ('type', 'parent', 'first_child', 'last_child', 'prev', 'next',
                 'literal', 'destination', 'title', 'info', 'level',
                 'list_data', 'is_fenced', 'fence_char', 'fence_length',
                 'fence_offset', 'html_block_type', 'open', 'last_line_blank',
                 'string_content', 'start_line')

    def __init__(self, type_, literal=None):
        self.type = type_
        self.parent = None
        self.first_child = None
        self.last_child = None
        self.prev = None
        self.next = None
        self.literal = literal
        self.destination = None
        self.title = None
        self.info = None
        self.level = 0
        self.list_data = None
        self.is_fenced = False
        self.fence_char = None
        self.fence_length = 0
        self.fence_offset = 0
        self.html_block_type = 0
        self.open = True
        self.last_line_blank = False
        self.string_content = ''
        self.start_line = 0

    @property
    def is_container(self):
        return self.type in CONTAINER_TYPES

    def append_child(self, child):
        child.unlink()
        child.parent = self
        if self.last_child is not None:
            self.last_child.next = child
            child.prev = self.last_child
            self.last_child = child
        else:
            self.first_child = child
            self.last_child = child

    def unlink(self):
        if self.prev is not None:
            self.prev.next = self.next
        elif self.parent is not None:
            self.parent.first_child = self.next
        if self.next is not None:
            self.next.prev = self.prev
        elif self.parent is not None:
            self.parent.last_child = self.prev
        self.parent = None
        self.next = None
        self.prev = None

    def insert_after(self, sibling):
        sibling.unlink()
        sibling.next = self.next
        if sibling.next is not None:
            sibling.next.prev = sibling
        sibling.prev = self
        self.next = sibling
        sibling.parent = self.parent
        if sibling.next is None and sibling.parent is not None:
            sibling.parent.last_child = sibling

    def children(self):
        child = self.first_child
        while child is not None:
            nxt = child.next
            yield child
            child = nxt

    def walk(self):
        """Iterative depth-first traversal yielding (node, entering)."""
        root = self
        cur = self
        entering = True
        while cur is not None:
            node, ent = cur, entering
            if ent and node.type in CONTAINER_TYPES:
                if node.first_child is not None:
                    cur = node.first_child
                    entering = True
                else:
                    entering = False
            elif node is root:
                cur = None
            elif node.next is None:
                cur = node.parent
                entering = False
            else:
                cur = node.next
                entering = True
            yield node, ent
