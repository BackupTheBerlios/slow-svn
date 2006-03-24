<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

  <xsl:template match="@*[normalize-space()]" mode="copyattr">
    <xsl:attribute name="{local-name()}">
      <xsl:value-of select="string()"/>
    </xsl:attribute>
  </xsl:template>
  <xsl:template match="@*" mode="copyattr"/>

</xsl:stylesheet>
