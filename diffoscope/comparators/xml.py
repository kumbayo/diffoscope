import re

from xml.dom import minidom
from diffoscope.difference import Difference
from diffoscope.comparators.utils.file import File
from xml.parsers.expat import ExpatError

def _format(node):
  """
  Removes *inplace* spaces from minidom.Document

  Args:
    node -- A xml.dom.minidom.Document object

  Returns:
    void
  """
  for n in node.childNodes:
    if n.nodeType == minidom.Node.TEXT_NODE:
      if n.nodeValue: n.nodeValue = n.nodeValue.strip()
    elif n.nodeType == minidom.Node.ELEMENT_NODE:
      _format(n)

def _parse(file):
  """
  Formats a minidom.Document file and returns XML as string.

  Args:
    file -- An io.TextIOWrapper object

  Returns:
    str: formated string object
  """
  xml = minidom.parse(file)
  _format(xml)
  xml.normalize()
  return xml.toprettyxml(indent=2*' ')


class XMLFile(File):
  """
  XML Files Comparison class

  Attributes:
    RE_FILE_EXTENSION (SRE_Pattern): xml file extension pattern
  """
  RE_FILE_EXTENSION = re.compile(r'\.xml$')

  @staticmethod
  def recognizes(file):
    """
    Identifies if a given file has XML extension

    Args:
      file - a diffoscope.comparators.utils.file.File object

    Returns:
      False if file is not a XML File, True otherwise
    """
    if XMLFile.RE_FILE_EXTENSION.search(file.name) is None:
      return False

    with open(file.path) as f:
      try:
        file.parsed = _parse(f)
      except ExpatError:
        return False

    return True

  def compare_details(self, other, source=None):
    """
    Compares self.object with another, returning a Difference object

    Args:
      other  -- A XMLFile object
      source

    Returns:
      A diffoscope.difference.Difference object
    """
    return [ Difference.from_text(self.dumps(self), self.dumps(other),
      self.path, other.path)]

  def dumps(self, file):
    """
    Opens a XMLFile and returns its parsed content

    Args:
      file -- XMLFile object

    Returns:
      str -- Formatted XML content from file
    """
    if file.parsed:
      return file.parsed

    with open(file.path) as f:
      return _parse(f)


