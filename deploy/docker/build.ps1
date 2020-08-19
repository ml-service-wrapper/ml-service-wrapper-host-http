
$imageName = "mlhttpservice"

Push-Location $PSScriptRoot\..\..\..;
Try {
    docker build -t $imageName -f "$PSScriptRoot\Dockerfile" .
}
Finally {
    Pop-Location
}
