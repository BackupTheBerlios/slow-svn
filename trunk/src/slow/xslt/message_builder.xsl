<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:msg="http://www.dvs1.informatik.tu-darmstadt.de/research/OverML/himdel"
  >

  <xsl:import href="common.xsl"/>
  <xsl:output method="xml" encoding="UTF-8" indent="no" />
  <xsl:strip-space elements="*"/>

  <xsl:param name="copy_toplevel">false</xsl:param>

  <xsl:template match="msg:message_hierarchy">
    <msg:messages>
      <xsl:apply-templates mode="messages"/>
      <xsl:if test="$copy_toplevel != 'false'">
	<xsl:copy-of select="msg:container"/>
	<xsl:copy-of select="msg:protocol"/>
      </xsl:if>
    </msg:messages>
  </xsl:template>

  <xsl:template match="msg:message">
    <msg:messages>
      <xsl:apply-templates select="." mode="messages"/>
    </msg:messages>
  </xsl:template>

  <xsl:template match="/*">
    <xsl:apply-templates select="msg:message_hierarchy" />
  </xsl:template>

  <xsl:template match="msg:message" mode="messages">
    <xsl:variable name="message" select="."/>
    <xsl:variable name="children">
      <xsl:apply-templates select="msg:*" mode="message"/>
      <xsl:apply-templates select="ancestor::msg:header[string(@access_name)]" mode="message"/>
    </xsl:variable>

    <xsl:variable name="typename" select="@type_name"/>
    <xsl:variable
	name="protocols"
	select="ancestor::msg:message_hierarchy/msg:protocol[msg:message-ref/@type_name = $typename]"/>

    <xsl:choose>
      <xsl:when test="$protocols">
	<xsl:for-each select="$protocols">
	  <msg:message>
	    <xsl:apply-templates select="$message/@access_name|$message/@type_name" mode="copyattr"/>
	    <xsl:copy-of select="$children"/>
	    <xsl:copy>
	      <xsl:apply-templates select="@access_name|@type_name" mode="copyattr"/>
	    </xsl:copy>
	  </msg:message>
	</xsl:for-each>
      </xsl:when>
      <xsl:otherwise>
	<xsl:copy>
	  <xsl:apply-templates select="@access_name|@type_name" mode="copyattr"/>
	  <xsl:copy-of select="$children"/>
	</xsl:copy>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <!-- headers -->
  <xsl:template match="msg:header[string(@access_name)]" mode="message">
    <xsl:copy>
      <xsl:apply-templates select="@*" mode="copyattr"/>
      <xsl:apply-templates select="msg:*"  mode="header"/>
    </xsl:copy>
  </xsl:template>
  <xsl:template match="msg:header" mode="message" />

  <xsl:template match="msg:header[not(string(@access_name))]" mode="header">
    <xsl:apply-templates select="msg:*" mode="header"/>
  </xsl:template>

  <xsl:template match="msg:content|msg:viewdata|msg:container|msg:container-ref" mode="header">
    <xsl:apply-templates select="." mode="message"/>
  </xsl:template>

  <xsl:template match="msg:*" mode="header" />

  <!-- message content -->
  <xsl:template match="msg:content|msg:viewdata" mode="message">
    <xsl:copy>
      <xsl:apply-templates select="@*" mode="copyattr"/>
    </xsl:copy>
  </xsl:template>

  <xsl:template match="msg:container[string(@access_name)]" mode="message">
    <xsl:copy>
      <xsl:apply-templates select="@access_name|@type_name" mode="copyattr"/>
      <xsl:apply-templates mode="message"/>
    </xsl:copy>
  </xsl:template>

  <xsl:template match="msg:container" mode="message">
    <xsl:apply-templates mode="message"/>
  </xsl:template>

  <xsl:template match="msg:container-ref[string(@access_name)]" mode="message">
    <msg:container>
      <xsl:apply-templates select="@access_name|@type_name" mode="copyattr"/>
      <xsl:variable name="typename" select="@type_name"/>
      <xsl:apply-templates
	  select="ancestor::msg:message_hierarchy/msg:container[@type_name = $typename]/msg:*"
	  mode="message"/>
    </msg:container>
  </xsl:template>

  <xsl:template match="msg:container-ref" mode="message">
    <xsl:variable name="typename" select="@type_name"/>
    <xsl:apply-templates
	select="ancestor::msg:message_hierarchy/msg:container[@type_name = $typename]/msg:*"
	mode="message"/>
  </xsl:template>
</xsl:stylesheet>
