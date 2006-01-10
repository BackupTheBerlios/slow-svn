<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:edsl="http://www.dvs1.informatik.tu-darmstadt.de/research/OverML/edsl">

  <xsl:import href="common.xsl"/>

  <xsl:output method="xml" encoding="UTF-8" indent="no" />

  <xsl:template match="edsl:edsm">
    <xsl:copy>
      <edsl:states>
	<xsl:apply-templates select="./edsl:states/edsl:state" mode="edsm"/>
	<xsl:apply-templates select=".//edsl:subgraph" mode="edsm"/>
      </edsl:states>
      <edsl:transitions>
	<xsl:apply-templates select=".//edsl:transition" mode="edsm"/>
      </edsl:transitions>
    </xsl:copy>
  </xsl:template>

  <xsl:template match="edsl:subgraph" mode="edsm">
    <xsl:variable name="id" select="@id"/>
    <xsl:for-each select="edsl:states/edsl:state">
      <xsl:copy>
	<xsl:attribute name="name">
	  <xsl:value-of select="concat($id, '_', @name)"/>
	</xsl:attribute>
	<xsl:apply-templates select="@*[local-name() != 'name']" mode="copyattr"/>
	<xsl:apply-templates select="edsl:*" mode="edsm"/>
      </xsl:copy>
    </xsl:for-each>
    <xsl:apply-templates select="edsl:states/edsl:subgraph" mode="edsm"/>
  </xsl:template>

  <!-- strip empty elements -->
  <xsl:template match="edsl:*[not (@* or * or normalize-space())]" mode="edsm"/>

  <!-- copy everything else -->
  <xsl:template match="edsl:*" mode="edsm">
    <xsl:copy>
      <xsl:apply-templates select="@*" mode="copyattr"/>
      <xsl:apply-templates select="edsl:*|text()" mode="edsm"/>
    </xsl:copy>
  </xsl:template>
</xsl:stylesheet>
