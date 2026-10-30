(FolderPath as text, TableName as text) as table =>
let
    Source = Csv.Document(File.Contents(FolderPath & "/" & TableName & ".csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true])
in
    Headers
