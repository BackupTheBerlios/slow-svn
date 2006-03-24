<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:math = "http://www.w3.org/1998/Math/MathML"
  xmlns:file = "http://www.dvs1.informatik.tu-darmstadt.de/research/OverML/slow"
  xmlns:sql  = "http://www.dvs1.informatik.tu-darmstadt.de/research/OverML/sql"
  xmlns:db   = "http://www.dvs1.informatik.tu-darmstadt.de/research/OverML/nala"
  xmlns:msg  = "http://www.dvs1.informatik.tu-darmstadt.de/research/OverML/himdel"
  xmlns:edsm = "http://www.dvs1.informatik.tu-darmstadt.de/research/OverML/edsl"
  xmlns:slosl= "http://www.dvs1.informatik.tu-darmstadt.de/research/OverML/slosl"
  >

  <xsl:import href="message_builder.xsl"/>
  <xsl:import href="flatten_edsm.xsl"/>
  <xsl:import href="common.xsl"/>

  <xsl:output method="xml" encoding="UTF-8" indent="no" />

  <xsl:template match="/file:file">
    <file:file
	xmlns:math = "http://www.w3.org/1998/Math/MathML"
	xmlns:file = "http://www.dvs1.informatik.tu-darmstadt.de/research/OverML/slow"
	xmlns:sql  = "http://www.dvs1.informatik.tu-darmstadt.de/research/OverML/sql"
	xmlns:db   = "http://www.dvs1.informatik.tu-darmstadt.de/research/OverML/nala"
	xmlns:msg  = "http://www.dvs1.informatik.tu-darmstadt.de/research/OverML/himdel"
	xmlns:edsm = "http://www.dvs1.informatik.tu-darmstadt.de/research/OverML/edsl"
	xmlns:slosl= "http://www.dvs1.informatik.tu-darmstadt.de/research/OverML/slosl"
	>
      <xsl:apply-templates select="file:types"       mode="file"/>
      <xsl:apply-templates select="db:attributes"    mode="file"/>
      <xsl:apply-templates select="msg:message_hierarchy"/>
      <xsl:apply-templates select="edsm:edsm"/>
      <xsl:apply-templates select="slosl:statements" mode="file"/>
    </file:file>
  </xsl:template>

  <xsl:template match="node()" mode="file">
    <xsl:copy>
      <xsl:apply-templates select="@*" mode="copyattr"/>
      <xsl:apply-templates mode="file"/>
    </xsl:copy>
  </xsl:template>

</xsl:stylesheet>
