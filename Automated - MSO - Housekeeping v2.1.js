/******
======================================================================================

Script:			MSO - Housekeeping Script
Version:		v2.0
Create date:	Mar 08 2016
Description:	Script to cleanup configured files and sub-folders as per retention period set in days.
				Cleanup will be done based on file/folder timestamp WITHOUT any checks on its reference to application.
				Retention information and respective actions are taken from MSO - Housekeeping Config Table (mso_housekeeping_config)
				IMPORTANT: 7ZIP is required as zipping is done using 7Z in this script.
				List of Actions: COPY, MOVE, DELETE, ARCHIVE, ORGANIZE
				v2.0 - Modified 7ZIP to GZIP through CYGWIN as 7ZIP is taking very long time to zip files. CYGWIN should be available in host machine as well as cygwin64\bin dir should be part of PATH env variable.
======================================================================================
******/

//Arugments Parse
var objArgs = WScript.Arguments;
var scriptMode = "ANALYZE";
if (objArgs.length != 1)
{
	WScript.Echo("Usage: " + WScript.ScriptName + " <Scripte Mode: ANALYZE/ACT>"); 
	WScript.Echo("Set Script Mode = ANALYZE for analyzing all retention locations configured in table instance MSO - Housekeeping Config Table (mso_housekeeping_config). Note that NO files or folders will be actioned in this mode."); 
	WScript.Echo("Set Script Mode = ACT for performing actions on respective retention locations as configured in table instance MSO - Housekeeping Config Table (mso_housekeeping_config).");
	WScript.Echo("Example: " + WScript.ScriptName + " ANALYZE");  
	WScript.Quit(1);
}
if (objArgs(0) != "ANALYZE" && objArgs(0) != "ACT") { WScript.Echo("First Parameter cannot be other than ANALYZE or ACT."); WScript.Quit(1); } else { scriptMode = objArgs(0); }

// Variables declaration for SMTP
var SMTPServer = "10.150.1.131";
var SMTPServerPort = 25; var SMTPSendOverNetwork = 2;
var emailFrom = "from email id";

var emailTo = "give the email ids here";

// Variables declaration for SQL Server Connection
var DP = "SQLOLEDB";
var DS = "d1";
var DB = "d2";
var UN = "d3";
var PWD = "d4";

var adOpenStatic = 3;
var adLockReadOnly = 1;
var adCmdText = 1;
var adUseClient = 3;

var strConn =
	"Provider="			+DP+
	";Initial Catalog="	+DB+
	";Data Source="		+DS+
	";User ID="			+UN+
	";Password="		+PWD+
	";"

// Variables declaration for SITE and ALERT properties
var site = "company";
var application = "ROCPS v9.9";
var serverIP = "10.150.33.152";
var alertCategory = "Operations Scripts";
var alertHeader = null;

// Other Variables declaration
var wugMsg = null;
var errMsg = null;
var resultVal = 0;
var gRetArray = new Array();
var copyActionLogText = new String();
var moveActionLogText = new String();
var deleteActionLogText = new String();
var archiveActionLogText = new String();
var orgActionLogText = new String();
var now = null;
var startTime=new Date();
var emailSubject = new String();
var emailText = new String();
var htmlText = new String();

var WshNetwork = WScript.CreateObject("WScript.Network");
var scriptDomain = WshNetwork.UserDomain;
var scriptMachine = WshNetwork.ComputerName;
var scriptUser = WshNetwork.UserName;

// Creating Array prototype indexOf, if it doesn't exist	
if(!Array.prototype.indexOf) 
{
	Array.prototype.indexOf = function(obj, start)
	{
		for (var i = (start || 0); i < this.length; i++)
		{
			if (this[i] === obj) { return i; }
		}
		return -1;
	}
}

// Creating Array prototype isArray, if it doesn't exist
if(!Array.prototype.isArray)
{ function isArray(myArray) { return myArray.constructor.toString().indexOf("Array") > -1; } }

// Creating Array prototype push, if it doesn't exist
if(!Array.prototype.push)
{ function push(myArray) { return Array.prototype.push.apply(this,arguments); } }

// Creating Array prototype pushUniq, if it doesn't exist
if(!Array.prototype.pushUniq)
{ Array.prototype.pushUniq = function (item){ if(this.indexOf(item) == -1) { this.push(item); return true; } return false; } }

try { var fso = new ActiveXObject("Scripting.FileSystemObject"); var connection = new ActiveXObject("ADODB.Connection"); connection.ConnectionTimeout=3000; connection.CommandTimeout=3000; connection.open(strConn); var shell = new ActiveXObject("WScript.Shell"); } catch (e) { throw "Scripting File System Object OR Connection OR Shell Object not found."; }

//====================================================================================

now = new Date(); WScript.Echo("Start DTTM = "+now); WScript.Echo("Script Mode = "+scriptMode); WScript.Echo();

try { main(); } catch (e) { errMsg = e.message; }

if (errMsg != null)
{
	WScript.Echo("Machine = " + scriptMachine + "\n" + "User = " + scriptUser + "\n" + "Script = " + WScript.ScriptFullName + "\n" + errMsg);
	sendEmail("JScript Error:: " + site + ' | ' + application + ' | ' + alertHeader, "Machine = " + scriptMachine + "<br>" + "User = " + scriptUser + "<br>" + "Script = " + WScript.ScriptFullName + "<hr>" + errMsg + "<br><hr>");

	WScript.Quit(1);
}

if (wugMsg == null)	{ resultVal = 0; wugMsg = "SCRIPT EXECUTION COMPLETE."; } else { resultVal = 1; wugMsg = wugMsg.replace(/^(null;)/,''); }

now = new Date(); WScript.Echo(); WScript.Echo("End DTTM = "+now);
WScript.Echo(wugMsg);

//====================================================================================

// All Functions definition
function main()
{
	try
	{
		alertHeader = "MSO - Housekeeping Script";
		
		try { var objSQLRs = new ActiveXObject("ADODB.Recordset"); var objRs = new ActiveXObject("ADODB.Recordset"); } catch (e) { errMsg = "ADODB namespace not found."; return false; }
		
		var rqSQL = "SELECT hsk_src_path [Source Path], hsk_action [Action], isnull(	hsk_dest_path,'NULL') [Destination Path], hsk_retention_days [Retention Days], hsk_include_subdirs [Include Sub Dirs], isnull(hsk_comments,'NULL') [Comments] FROM [" +DB+"].[dbo].mso_housekeeping_config order by hsk_id;"

		try { objRs.CursorLocation = adUseClient; objRs.open(rqSQL, connection, adOpenStatic, adLockReadOnly, adCmdText); } catch (e) { errMsg = "rqSQL Query errored: <br>" + e.message; return false; }

		WScript.Echo("Number of entries in MSO - Housekeeping Config Table (mso_housekeeping_config): " + objRs.RecordCount);
		if (objRs.RecordCount > 0)
		{
			emailSubject = site + ' | ' + application + ' | ' + alertHeader;
			
			var objhtmlIt = new htmlIt();
			var objTagger = new tblTagger();
			var tblData = new String();

			objRs.MoveFirst();
			while (objRs.EOF != true) 
			{
				htmlText = objhtmlIt.start(); htmlText += objhtmlIt.bodyStart(); htmlText += objhtmlIt.bodyLine("MyText1","Hello,");

				WScript.Echo("_____________________________________________________________________________________\n");
				for (var i=0; i<objRs.fields.count; i++) { WScript.Echo(objRs.fields(i).name + ": " + objRs(objRs.fields(i).name)); }
				WScript.Echo("\n");
				
				if (objRs("Action").value === "NONE") { WScript.Echo("NO ACTION"); objRs.MoveNext(); continue; }
				
				var configCheck = new String();
				if(objRs("Action").value != "NONE" && objRs("Action").value != "COPY" && objRs("Action").value != "MOVE" && objRs("Action").value != "DELETE" && objRs("Action").value != "ARCHIVE" && objRs("Action").value != "ORGANIZE") 
				{ configCheck = "Action unknown or not defined."; }
				else if(!fso.FolderExists(objRs("Source Path").value))
				{ configCheck = "'Source Path' don't exist."; }
				else if ((objRs("Action").value === "COPY" || objRs("Action").value === "MOVE") && !fso.FolderExists(objRs("Destination Path").value))
				{ configCheck = "'Destination Path' don't exist and its mandatory field for this action."; }

				if (configCheck != "")
				{
					WScript.Echo(configCheck);
					htmlText += objhtmlIt.bodyLine("MyText1",configCheck);
					
					tblData = objTagger.tblStart("myTable1");
					tblData += objTagger.open(); for (var i=0; i<objRs.fields.count; i++) { tblData += objTagger.header(objRs.fields(i).name); } tblData += objTagger.close();
					tblData += objTagger.open(); for (i=0; i<objRs.fields.count; i++) { tblData += objTagger.value(objRs(objRs.fields(i).name)); } tblData += objTagger.close();
					tblData += objTagger.tblEnd();

					htmlText += tblData;
					htmlText += objhtmlIt.recommendedAction(
								["Correct configuration in Table Instance Search Screen > MSO - Housekeeping Config Table. Table Name: mso_retention_config_tbl.",
								"Permitted Actions: COPY, MOVE, DELETE, ARCHIVE, ORGANIZE & NONE."]
								);
					htmlText += objhtmlIt.bottomInfo("N/A");
					htmlText += objhtmlIt.end();	

					//WScript.Echo(htmlText);
					sendEmail("[!] " + emailSubject, htmlText);
					objRs.MoveNext();
					continue;
				}				
				
				var srcPath = objRs("Source Path").value.replace(/\//g,'\\'); // replaces / by \ and stores in this variable
				var destPath = objRs("Destination Path").value.replace(/\//g,'\\'); // replaces / by \ and stores in this variable

				gRetArray = Array();
				var filesArray	= FolderFileList(srcPath, objRs("Include Sub Dirs").value, objRs("Retention Days").value);

				for (var i=0; i<filesArray.length; i++) 
				{ 
					if (filesArray[i] != srcPath)
					{ 
						//if (fso.FolderExists(filesArray[i])) { if (EmptyFolder(filesArray[i])) { WScript.Echo("Empty Folder"); } else { WScript.Echo("Not an empty Folder"); } } else { WScript.Echo("Not a Folder"); }
						if (objRs("Action").value === "COPY") 			{ CopyAction(filesArray[i],srcPath,destPath); }
						else if (objRs("Action").value === "MOVE") 		{ MoveAction(filesArray[i],srcPath,destPath); }
						else if (objRs("Action").value === "DELETE") 	{ DeleteAction(filesArray[i]); }
						else if (objRs("Action").value === "ARCHIVE") 	{ ArchiveAction(filesArray[i],srcPath,destPath); }
						else if (objRs("Action").value === "ORGANIZE") 	{ OrganizeAction(filesArray[i],srcPath); }
						else { WScript.Echo("ACTION UNKNOWN OR NOT DEFINED"); }
					} 
				}
				objRs.MoveNext();
			}
			objRs.Close();
		}
	} catch (e) { errMsg = e.message; return false; }
}

//*************************************************************************************************************************************************************************

// Function to quote RegExp input string's special characters
function RegExpQuote(item) { return item.replace(/([.?*+^$[\]\\(){}|-])/g, "\\$1"); }

//*************************************************************************************************************************************************************************

// Folder files listing Function
function FolderFileList(fldrAbsPath, includeSub, retDays)
{
	var fileCounter = 0;
	var s = "";
	var f = fso.GetFolder(fldrAbsPath);
	
	//WScript.Echo("Source Path" + "," + "Grand Parent Folder" + "," + "Parent Folder" + "," + "File" + "," + "Date Created" + "," + "Last Modified" + "," + "File Age Days");
	
	if (includeSub == "Y") 
	{
		// recurse subfolders
		var subfolders = new Enumerator(f.SubFolders);
		for(; !subfolders.atEnd(); subfolders.moveNext()){ s+=FolderFileList((subfolders.item()).path, includeSub, retDays); }  		
	}

	// display all file path names.
	var fc = new Enumerator(f.files);
	
	for (; !fc.atEnd(); fc.moveNext())
	{
		//var fileAgeHours = ((startTime - fc.item().DateLastModified)/(1000*60*60));
		var fileAgeDays = Math.round((startTime - fc.item().DateLastModified)/(3600000*24));
		if (fileAgeDays > retDays)
		{
			gRetArray.push(fc.item().Path);
			//WScript.Echo(fc.item().Path+ "," +fc.item().ParentFolder.ParentFolder.Name+ "," +fc.item().ParentFolder.Name+ "," +fc.item().Name+ "," +fc.item().DateCreated+ "," +fc.item().DateLastModified+ "," +fileAgeDays);
			fileCounter++;
		}
	}
	if (includeSub == "Y" && (fileAgeDays > retDays || EmptyFolder(fldrAbsPath))) { /*WScript.Echo(f.path);*/ gRetArray.push(f.Path); }
	return(gRetArray);
}

//*************************************************************************************************************************************************************************

// Function to check is folder empty i.e. no files or subfolders.
function EmptyFolder(emFldrAbsPath)
{
	if (fso.FolderExists(emFldrAbsPath)) 
	{
		//If input folder dont have any files or subfolders then returns TRUE (1). Else, returns FALSE (0)
		if (fso.GetFolder(emFldrAbsPath).Files.Count == 0 && fso.GetFolder(emFldrAbsPath).SubFolders.Count == 0) 
		{ return 1; } else { return 0; }
	}
	else { return 0; } // 1 means TRUE; 0 means FALSE
}

//*************************************************************************************************************************************************************************

// Function to create sub directories. 
function CreateSubDirs(sbFldrAbsPath)
{
	if(sbFldrAbsPath.substr(sbFldrAbsPath.length-1,1) != "\\" ) { sbFldrAbsPath=sbFldrAbsPath+"\\"; }

	var inputStr = sbFldrAbsPath.replace(/\\\\/,'XX');
	var pos = -1;
	var prevPos = 0;
	var newFldr = new String();

	while (newFldr+"\\" != sbFldrAbsPath)
	{
		pos = inputStr.indexOf("\\");
		newFldr = sbFldrAbsPath.substring(0,prevPos+pos);
		//if (fso.FolderExists(newFldr)) { WScript.Echo(newFldr, "folder exist"); } else { WScript.Echo(newFldr, "folder don't exist"); try { fso.CreateFolder(newFldr); } catch (e) {} }		
		if (!fso.FolderExists(newFldr)) { try { fso.CreateFolder(newFldr); } catch (e) {} }	
		inputStr=inputStr.slice(pos+1);
		prevPos=prevPos+pos+1;
	}
}

//*************************************************************************************************************************************************************************

// COPY ACTION Function: Absolute path with file name, source absolute path, destination absolute path
function CopyAction(cpFldrAbsPath,cpSrcPath,cpDestPath)
{
	if (fso.FolderExists(cpFldrAbsPath)) { var parentFldr = fso.GetFolder(cpFldrAbsPath).ParentFolder.Path; }
	else { var parentFldr = fso.GetFile(cpFldrAbsPath).ParentFolder.Path; }
	
	var rgExp = new RegExp(RegExpQuote(cpSrcPath),"i");
	var parentFldrDest = parentFldr.replace(rgExp,cpDestPath);

	if (!fso.FolderExists(parentFldrDest)) 
	{ 
		copyActionLogText = parentFldrDest + " :: New Folder";
		if (objArgs(0) != "ACT") { WScript.Echo(copyActionLogText + " :: WILL BE CREATED"); }
		else { CreateSubDirs(parentFldrDest); WScript.Echo(copyActionLogText + " :: CREATED"); } 
	}
	if (!fso.FolderExists(cpFldrAbsPath)) 
	{
		copyActionLogText = cpFldrAbsPath;
		if (objArgs(0) != "ACT") { WScript.Echo(copyActionLogText + " :: WILL BE COPIED TO :: "+parentFldrDest); }
		else { fso.CopyFile(cpFldrAbsPath,parentFldrDest+"\\"); WScript.Echo(copyActionLogText + " :: COPIED TO :: "+parentFldrDest); }		
	}
}

//*************************************************************************************************************************************************************************

// MOVE ACTION Function
function MoveAction(mvFldrAbsPath,mvSrcPath,mvDestPath) 
{
	moveActionLogText = mvFldrAbsPath;
	if (objArgs(0) != "ACT") { WScript.Echo(moveActionLogText + " :: WILL BE MOVED FROM :: " + mvSrcPath + " :: TO :: " + mvDestPath); }
	else 
	{ 
		CopyAction(mvFldrAbsPath,mvSrcPath,mvDestPath);

		if (fso.FolderExists(mvFldrAbsPath)) { var mvParentFldr = fso.GetFolder(mvFldrAbsPath).ParentFolder.Path; }
		else { var mvParentFldr = fso.GetFile(mvFldrAbsPath).ParentFolder.Path; }
	
		var rgExp = new RegExp(RegExpQuote(mvSrcPath),"i");
		var mvParentFldrDest = mvParentFldr.replace(rgExp,mvDestPath);
		
		var compareFrom = new String("source");
		var compareTo = new String("dest");
		try
		{
			if (fso.FileExists(mvFldrAbsPath)) { var compareFrom = fso.GetFile(mvFldrAbsPath).Path; }
			if (fso.FileExists(mvParentFldrDest+"\\"+fso.GetFile(mvFldrAbsPath).Name)) { var compareTo = fso.GetFile(mvParentFldrDest+"\\"+fso.GetFile(mvFldrAbsPath).Name).Path; }			
		} catch (e) {}

	
		if (compareFrom === compareTo) 
		{
			WScript.Echo("CANNOT DELETE AS " + mvFldrAbsPath + " AND " + mvParentFldrDest+"\\"+fso.GetFile(mvFldrAbsPath).Name + " ARE SAME."); 
			
		}
		else if (fso.FileExists(compareTo))
		{ 
			DeleteAction(mvFldrAbsPath); 
		}
		else { WScript.Echo("CANNOT DELETE " + mvFldrAbsPath + " AS DESTINATION IS SAME AS SOURCE OR DESTINATION DON'T EXIST."); }
	}
}

//*************************************************************************************************************************************************************************

// DELETE ACTION Function
function DeleteAction(dlFldrAbsPath)
{
	if (fso.FolderExists(dlFldrAbsPath)) 
	{ 
		if (EmptyFolder(dlFldrAbsPath)) 
		{ 
			deleteActionLogText = dlFldrAbsPath + " :: Empty Folder";
			if (objArgs(0) != "ACT") { WScript.Echo(deleteActionLogText + " :: WILL BE DELETED"); }	
			else { fso.DeleteFolder(dlFldrAbsPath); WScript.Echo(deleteActionLogText + " :: DELETED"); }
		} else { WScript.Echo(dlFldrAbsPath + " :: Not an Empty Folder :: NO ACTION"); } 
	} 
	else 
	{
		deleteActionLogText = dlFldrAbsPath + " :: File";
		if (objArgs(0) != "ACT") { WScript.Echo(deleteActionLogText + " :: WILL BE DELETED"); } 
		else { fso.GetFile(dlFldrAbsPath).Delete(); WScript.Echo(deleteActionLogText + " :: DELETED"); }
	}
}

//*************************************************************************************************************************************************************************

// ARCHIVE ACTION Function
function ArchiveAction(arFldrAbsPath,arSrcPath,arDestPath)
{
	if (!fso.FolderExists(arFldrAbsPath) && fso.GetFile(arFldrAbsPath).Type != "7Z File" && fso.GetFile(arFldrAbsPath).Type != "GZ File" && fso.GetFile(arFldrAbsPath).Type != "ZIP File")  
	{
		archiveActionLogText = arFldrAbsPath + " :: File";
		//WScript.Echo(archiveActionLogText + " :: WIP");
		if (objArgs(0) != "ACT") { WScript.Echo(archiveActionLogText + " :: WILL BE ARCHIVED"); } 
		else 
		{ 
			//var zipRet = shell.Run("7z a -bd -tgzip -mx9 \"" + arFldrAbsPath + ".gz\" \"" + arFldrAbsPath + "\" -w\"" + fso.GetFile(arFldrAbsPath).ParentFolder.Path + "\"", 0, true);
			//WScript.Echo("gzip \"" + arFldrAbsPath.replace(/\\/g,'\/') + "\"");
			var zipRet = shell.Run("gzip \"" + arFldrAbsPath.replace(/\\/g,'\/') + "\"", 0, true);

			if (zipRet === 0) 
			{ 
				if (fso.FileExists(arFldrAbsPath) && fso.FileExists(arFldrAbsPath+ ".gz")) { fso.DeleteFile(arFldrAbsPath); }
			} else { errMsg += "Error in archiving:" + arFldrAbsPath; return false; }
			WScript.Echo(archiveActionLogText + " :: ARCHIVED"); 
		}
		if (fso.FolderExists(arDestPath)) { MoveAction(arFldrAbsPath+ ".gz",arSrcPath,arDestPath); }
	}
}

//*************************************************************************************************************************************************************************

// ORGANIZE ACTION Function
function OrganizeAction(orFldrAbsPath,orSrcPath)
{
	if (!fso.FolderExists(orFldrAbsPath))  
	{
		orgActionLogText = fso.GetFile(orFldrAbsPath).Name + " :: File";
		var fileName = fso.GetFile(orFldrAbsPath).Name;
		var dteMdfd = new Date(fso.GetFile(orFldrAbsPath).DateLastModified);
		var orgFldr = dteMdfd.toDateString().slice(4).replace(/ [0-9]{1,2} /,'-');
		var orgDest = fso.GetFile(orFldrAbsPath).ParentFolder.Path + "\\" + orgFldr + "\\";
		if (orgFldr != fso.GetFile(orFldrAbsPath).ParentFolder.Name)
		{
			//WScript.Echo(orgActionLogText + " :: BEING ORGANIZED TO :: " + orgFldr)
			if (objArgs(0) != "ACT") { WScript.Echo(orgActionLogText + " :: WILL BE ORGANIZED TO :: " + orgFldr); } 
			else 
			{
				MoveAction(orFldrAbsPath,orSrcPath,orgDest);
				WScript.Echo(orgActionLogText + " :: ORGANIZED TO :: " + orgFldr); 
			}
		}
	}
}

//*************************************************************************************************************************************************************************

// HTML IT Function
function htmlIt()
{
	var retHtml = new String();

	// Function to set HTML head block with format details
	this.start = function () 
	{
		retHtml =
			"<html>\n" +
			"<head>\n<style type=\"text/css\">\n" + 
			"table.myTable1 { border-collapse:collapse;font-size:x-small; }\n" +
			"table.myTable1 th, table.myTable1 td { border:1px solid gray; padding:5px;text-align:left;font-family:\"Courier New\",Courier,Arial,Monospace;color:black; }\n" +
			"table.myTable1 th { background-color:lightgrey; }\n" +
			"table.myTable2 { border-collapse:collapse;font-size:x-small; }\n" +
			"table.myTable2 td { border:1px solid white; padding:5px;text-align:left;font-family:\"Courier New\",Courier,Arial,Monospace;color:white;background-color:#868686; }\n" +
			"p.MyText1 { font-family:\"Courier New\",Courier,Arial,Monospace;font-size:x-small;color:black; }\n" +
			"p.MyText2 { font-family:\"Courier New\",Courier,Arial,Monospace;font-size:x-small;color:#660000; }\n" +
			"td.highlight { background-color:yellow;font-weight:bold; }\n" +
			"ol.a { font-family:\"Courier New\",Courier,Arial,Monospace;font-size:x-small;color:black; }\n" +
			"</style>\n</head>\n";
		return (retHtml);
	}

	// Function to start HTML body
	this.bodyStart = function () { retHtml = "<body>\n"; return (retHtml); }

	// Function to capture HTML body. Accepts one line at a time. Body line text is input parameter.
	this.bodyLine = function (txtClass, bodyLineText) { retHtml = "<p class=" + txtClass + ">" + bodyLineText + "<br></p>\n"; return (retHtml); }

	// Function to end HTML body
	this.bodyEnd = function () { retHtml = "</body>\n"; return (retHtml); }

	// Function for Recommended Action
	this.recommendedAction = function (contextRAction)
	{
		var gNteActnArray = [
			//"If NOT SCHEDULED count is greater than zero, then look at attached log for \"Status Reason\".",
			//"Correct respective files accordingly and reimport them.",
			//"Note that, when Script Mode = ANALYZE, NO files will be scheduled for import. Import tasks will be scheduled only when Script Mode = ACT.",
			"Please reach out to company Managed Services Team for any other assistance on this regards."
		];

		var rActnText = this.bodyLine("MyText2","<u>RECOMMENDED ACTION:</u>");
		rActnText += "<ol class=a>\n";

		if (isArray(contextRAction)) { finalRArray = contextRAction.concat(gNteActnArray); } else { finalRArray = gNteActnArray };

		for (var i=0; i<finalRArray.length; i++)
		{
			rActnText += "<li>" + finalRArray[i] + "</li>\n";
		}
		rActnText += "</ol>\n";
		return (rActnText);
	}

	// Function for Bottom Info Table
	this.bottomInfo = function (monitorRange)
	{
		var objBtmTbl = new tblTagger();

		retHtml = 
			objBtmTbl.tblStart("myTable2") +
			objBtmTbl.value("SITE: " + site) +
			objBtmTbl.value("APPLICATION: " + application) +
			objBtmTbl.value("SERVER IP: " + serverIP) +
			objBtmTbl.value("DB: " + DB) +
			objBtmTbl.value("MONITOR RANGE: " + monitorRange) +
			objBtmTbl.value("ALERT CATEGORY: " + alertCategory) +
			objBtmTbl.tblEnd();

		return (retHtml);
	}

	this.end = function ()
	{
		var sentTime = new Date();

		retHtml = "<br><hr>\n";
		//retHtml += "<p class=MyText1>This email was sent on " + sentTime + ". Script: "+ WScript.ScriptFullName +"</p>\n";
		retHtml += "<p class=MyText1>This email was sent on " + sentTime + ".</p>\n";
		retHtml += "</body>\n</html>";
		return (retHtml);
	}
}

//*************************************************************************************************************************************************************************

// HTML Table Tagger Function
function tblTagger()
{
	var tagdText = new String();

	this.tblStart = function (tblClass) { tagdText = "<table class=" + tblClass + ">\n"; return (tagdText); } 

	this.open = function () { tagdText = "<tr>\n"; return (tagdText); }

	this.header = function (thValue) { tagdText = "<th>"+thValue+"</th>"; return (tagdText); }

	this.value = function (tdValue, tdClass) { tdClass = tdClass || "default"; tagdText = "<td class="+tdClass+">"+tdValue+"</td>"; return (tagdText); }

	this.close = function () { tagdText = "\n</tr>\n"; 	return (tagdText); }

	this.tblEnd = function () { tagdText = "</table>\n<br>"; return (tagdText); } 
}

//*************************************************************************************************************************************************************************

// Send Email Function
function sendEmail(emailSubject, emailBody)
{
	try
	{
		var oMsg = new ActiveXObject("CDO.Message");

		oMsg.Configuration.Fields.Item("http://schemas.microsoft.com/cdo/configuration/smtpserver")=SMTPServer;
		oMsg.Configuration.Fields.Item("http://schemas.microsoft.com/cdo/configuration/smtpserverport")=SMTPServerPort;
		oMsg.Configuration.Fields.Item("http://schemas.microsoft.com/cdo/configuration/sendusing")=SMTPSendOverNetwork;
		oMsg.Configuration.Fields.Update();

		oMsg.From		= emailFrom;
		oMsg.To			= emailTo;
		oMsg.Subject	= emailSubject;
		oMsg.HTMLBody	= emailBody;
		oMsg.Fields.Update();

		oMsg.Send();
	}
	catch (e)
	{
		errMsg = "Email Error: <br>" + e.message;
	}
}

//*************************************************************************************************************************************************************************

// Send Email with Attachment Function
function sendEmailAttach(emailSubject, emailBody, attachFile)
{
	try
	{
		var oMsg = new ActiveXObject("CDO.Message");

		oMsg.Configuration.Fields.Item("http://schemas.microsoft.com/cdo/configuration/smtpserver")=SMTPServer;
		oMsg.Configuration.Fields.Item("http://schemas.microsoft.com/cdo/configuration/smtpserverport")=SMTPServerPort;
		oMsg.Configuration.Fields.Item("http://schemas.microsoft.com/cdo/configuration/sendusing")=SMTPSendOverNetwork;
		oMsg.Configuration.Fields.Update();

		oMsg.From		= emailFrom;
		oMsg.To			= emailTo;
		oMsg.Subject	= emailSubject;
		oMsg.HTMLBody	= emailBody;
		oMsg.AddAttachment(attachFile);
		oMsg.Fields.Update();

		oMsg.Send();
	}
	catch (e)
	{
		errMsg = "Email Error: <br>" + e.message;
	}
}

//*************************************************************************************************************************************************************************
