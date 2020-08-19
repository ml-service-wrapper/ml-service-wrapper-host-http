
$imageName = "mlhttpservice"

Push-Location $PSScriptRoot;
Try {
    .\build.ps1
}
Finally {
    Pop-Location
}

docker stop $imageName
docker rm $imageName
    
docker run -d `
    -p 80 `
    -p 443 `
    --name $imageName `
    $imageName
