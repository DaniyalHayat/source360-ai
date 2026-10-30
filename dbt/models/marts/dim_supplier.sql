select * from {{ source('landing', 'dim_supplier') }}
