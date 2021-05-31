On Error Resume Next

Sub includeFile (fSpec)
    dim fileSys, file, fileData
    set fileSys=createObject ("Scripting.FileSystemObject")
    set file= fileSys.openTextFile(fSpec)
    fileData=file.readAll()
    file.close
    executeGlobal fileData
    set file = nothing
    set fileSys=nothing
End Sub
