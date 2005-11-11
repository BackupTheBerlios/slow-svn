<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:edsm="http://www.dvs1.informatik.tu-darmstadt.de/research/OverML/edsm">

  <xsl:import href="common.xsl"/>

  <xsl:output method="xml" encoding="UTF-8" indent="no" />

  <xsl:template match="edsm:edsm">
    <xsl:copy>
      <edsm:states>
	<xsl:apply-templates select="./edsm:states/edsm:state" mode="edsm"/>
	<xsl:apply-templates select=".//edsm:subgraph" mode="edsm"/>
      </edsm:states>
      <edsm:transitions>
	<xsl:apply-templates select=".//edsm:transition" mode="edsm"/>
      </edsm:transitions>
    </xsl:copy>
  </xsl:template>

  <xsl:template match="edsm:subgraph" mode="edsm">
    <xsl:variable name="id" select="@id"/>
    <xsl:for-each select="edsm:states/edsm:state">
      <xsl:copy>
	<xsl:attribute name="name">
	  <xsl:value-of select="concat($id, '_', @name)"/>
	</xsl:attribute>
	<xsl:apply-templates select="@*[local-name() != 'name']" mode="copyattr"/>
	<xsl:apply-templates select="edsm:*" mode="edsm"/>
      </xsl:copy>
    </xsl:for-each>
    <xsl:apply-templates select="edsm:states/edsm:subgraph" mode="edsm"/>
  </xsl:template>

  <!-- strip empty elements -->
  <xsl:template match="edsm:*[not (@* or * or normalize-space())]" mode="edsm"/>

  <!-- copy everything else -->
  <xsl:template match="edsm:*" mode="edsm">
    <xsl:copy>
      <xsl:apply-templates select="@*" mode="copyattr"/>
      <xsl:apply-templates select="edsm:*|text()" mode="edsm"/>
    </xsl:copy>
  </xsl:template>
</xsl:stylesheet>
