"""Document tree node shared by the block parser, inline parser and renderer."""


class ListData:
    __slots__ = ('type', 'tight', 'bullet_char', 'start', 'delimiter',
                 'padding', 'marker_offset')

    def __init__(self, marker_offset=0):
        self.type = None
        self.tight = True
        self.bullet_char = None
        self.start = None
        self.delimiter = None
        self.padding = None
        self.marker_offset = marker_offset

    def copy(self):
        other = ListData(self.marker_offset)
        other.type = self.type
        other.tight = self.tight
        other.bullet_char = self.bullet_char
        other.start = self.start
        other.delimiter = self.delimiter
        other.padding = self.padding
        return other


CONTAINER_TYPES = frozenset([
    'document', 'block_quote', 'list', 'item', 'paragraph', 'heading',
    'emph', 'strong', 'link', 'image',
])


class Node:
    __slots__ = ('type', 'parent', 'first_child', 'last_child', 'prev', 'next',
                 'literal', 'open', 'string_content', 'string_parts',
                 'start_line', 'end_line',
                 'list_data', 'info', 'destination', 'title', 'is_fenced',
                 'fence_char', 'fence_length', 'fence_offset', 'level',
                 'html_block_type')

    def __init__(self, node_type, literal=None):
        self.type = node_type
        self.parent = None
        self.first_child = None
        self.last_child = None
        self.prev = None
        self.next = None
        self.literal = literal
        self.open = True
        self.string_content = ''
        self.string_parts = None
        self.start_line = 0
        self.end_line = 0
        self.list_data = None
        self.info = None
        self.destination = None
        self.title = None
        self.is_fenced = False
        self.fence_char = None
        self.fence_length = 0
        self.fence_offset = 0
        self.level = 0
        self.html_block_type = 0

    def content(self):
        """Return the accumulated raw text content of a leaf block."""
        if self.string_parts:
            self.string_content += ''.join(self.string_parts)
            self.string_parts = None
        return self.string_content

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
        """Yield (node, entering) pairs in document order, iteratively."""
        stack = [(self, True)]
        while stack:
            node, entering = stack.pop()
            yield node, entering
            if entering and node.type in CONTAINER_TYPES:
                stack.append((node, False))
                child = node.last_child
                while child is not None:
                    stack.append((child, True))
                    child = child.prev
